from airflow.sdk import dag, task
from datetime import datetime, timedelta
from common import collect_rss

default_args = {
    'owner': 'airflow',
    'retries': 2,
    'retry_delay': timedelta(minutes=5),
}

SOURCES = [
    {"source_id": 3, "category_id": 1, "rss_url": "https://www.mk.co.kr/rss/30200030/"},
    {"source_id": 4, "category_id": 2, "rss_url": "https://www.mk.co.kr/rss/30100041/"},
    {"source_id": 5, "category_id": 3, "rss_url": "https://www.mk.co.kr/rss/50400012/"},
]


@dag(
    dag_id="mk_collect",
    default_args=default_args,
    schedule="*/30 * * * *",
    start_date=datetime(2026, 1, 1),
    catchup=False,
    is_paused_upon_creation=False,
    tags=["collect", "mk"],
)
def mk_dag():

    @task
    def collect_politics():
        s = SOURCES[0]
        return collect_rss(s["source_id"], s["category_id"], s["rss_url"])

    @task
    def collect_economy():
        s = SOURCES[1]
        return collect_rss(s["source_id"], s["category_id"], s["rss_url"])

    @task
    def collect_society():
        s = SOURCES[2]
        return collect_rss(s["source_id"], s["category_id"], s["rss_url"])

    collect_politics()
    collect_economy()
    collect_society()


mk_dag()