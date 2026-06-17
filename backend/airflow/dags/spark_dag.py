from airflow.sdk import dag, task
from datetime import datetime, timedelta
import subprocess
import os
import logging

logger = logging.getLogger(__name__)

default_args = {
    "owner": "airflow",
    "retries": 1,
    "retry_delay": timedelta(minutes=10),
}

SPARK_MASTER    = os.getenv("SPARK_MASTER_URL", "spark://spark-master:7077")
SPARK_JOBS_PATH = os.getenv("SPARK_JOBS_PATH", "/opt/airflow/spark/jobs")
PG_JAR_PATH     = os.getenv("PG_JAR_PATH", "/opt/spark/jars/postgresql-42.7.3.jar")
SPARK_CONTAINER = os.getenv("SPARK_CONTAINER", "news_spark_master")


def _run_spark_job(job_file: str, extra_conf: dict = None) -> dict:
    spark_submit_cmd = [
        "/opt/spark/bin/spark-submit",
        "--master", SPARK_MASTER,
        "--deploy-mode", "client",
        "--jars", PG_JAR_PATH,
        "--conf", "spark.python.worker.reuse=true",
        f"--conf=spark.executor.memory={os.getenv('SPARK_EXECUTOR_MEMORY', '2g')}",
        f"--conf=spark.driver.memory={os.getenv('SPARK_DRIVER_MEMORY', '1g')}",
    ]

    if extra_conf:
        for k, v in extra_conf.items():
            spark_submit_cmd += [f"--conf={k}={v}"]


    spark_submit_cmd.append(f"/opt/spark/jobs/{job_file}")


    cmd = ["docker", "exec"]

    # 환경변수
    env_vars = {
        "POSTGRES_HOST":     os.getenv("POSTGRES_HOST", "postgres"),
        "POSTGRES_PORT":     os.getenv("POSTGRES_PORT", "5432"),
        "POSTGRES_DB":       os.getenv("POSTGRES_DB", "news_rag"),
        "POSTGRES_USER":     os.getenv("POSTGRES_USER", "news_user"),
        "POSTGRES_PASSWORD": os.getenv("POSTGRES_PASSWORD", "news_password"),
        "EMBED_MODEL":       os.getenv("EMBED_MODEL", "jhgan/ko-sroberta-multitask"),
        "EMBED_BATCH_SIZE":  os.getenv("EMBED_BATCH_SIZE", "32"),
    }
    for k, v in env_vars.items():
        cmd += ["-e", f"{k}={v}"]

    cmd += [SPARK_CONTAINER] + spark_submit_cmd

    logger.info(f"spark-submit 실행: {' '.join(spark_submit_cmd)}")

    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=int(os.getenv("SPARK_JOB_TIMEOUT", "1800")),
    )

    if result.returncode != 0:
        logger.error(f"Spark Job 실패:\nSTDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}")
        raise RuntimeError(f"Spark Job {job_file} 실패 (returncode={result.returncode})")

    logger.info(f"Spark Job 완료:\n{result.stdout[-2000:]}")
    return {"returncode": result.returncode, "stdout_tail": result.stdout[-500:]}


@dag(
    dag_id="spark_pipeline",
    default_args=default_args,
    schedule="0 * * * *",
    start_date=datetime(2026, 1, 1),
    catchup=False,
    is_paused_upon_creation=False,
    tags=["spark", "embedding", "dedup"],
)
def spark_pipeline_dag():

    @task
    def check_unprocessed_count() -> int:
        import psycopg2
        conn = psycopg2.connect(
            host=os.getenv("POSTGRES_HOST", "postgres"),
            port=int(os.getenv("POSTGRES_PORT", "5432")),
            dbname=os.getenv("POSTGRES_DB", "news_rag"),
            user=os.getenv("POSTGRES_USER", "news_user"),
            password=os.getenv("POSTGRES_PASSWORD", "news_password"),
        )
        try:
            cur = conn.cursor()
            cur.execute("""
                SELECT COUNT(*) FROM articles
                WHERE is_processed = false
                  AND is_duplicate = false
                  AND description IS NOT NULL
                  AND length(description) >= 20
            """)
            count = cur.fetchone()[0]
            logger.info(f"미처리 기사 수: {count}")
            return count
        finally:
            conn.close()

    @task
    def run_embedding_job(unprocessed_count: int) -> dict:
        if unprocessed_count == 0:
            logger.info("처리할 기사 없음. embedding_job 스킵.")
            return {"skipped": True, "processed": 0}

        logger.info(f"embedding_job 시작: {unprocessed_count}건 처리 예정")
        return _run_spark_job("embedding_job.py")

    @task
    def run_dedup_job(embedding_result: dict) -> dict:
        if embedding_result.get("skipped"):
            logger.info("embedding_job 스킵됨. dedup_job도 스킵.")
            return {"skipped": True, "duplicates_found": 0}

        logger.info("dedup_job 시작")
        return _run_spark_job(
            "dedup_job.py",
            extra_conf={"spark.executor.memory": "1g"},
        )

    @task
    def notify_result(embedding_result: dict, dedup_result: dict):
        logger.info("=" * 50)
        logger.info("Spark 파이프라인 완료")
        logger.info(f"  embedding_job: {embedding_result}")
        logger.info(f"  dedup_job:     {dedup_result}")
        logger.info("=" * 50)

    count     = check_unprocessed_count()
    emb_res   = run_embedding_job(count)
    dedup_res = run_dedup_job(emb_res)
    notify_result(emb_res, dedup_res)


spark_pipeline_dag()