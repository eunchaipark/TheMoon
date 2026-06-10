from airflow.sdk import dag, task
from datetime import datetime, timedelta
from common import collect_rss

default_args = {
    'owner': 'airflow',
    'retries': 2,
    'retry_delay': timedelta(minutes=5),
}

SOURCES = [
    {"source_id": 1, "category_id": 1, "rss_url": "https://www.yna.co.kr/rss/politics.xml"},
    {"source_id": 2, "category_id": 2, "rss_url": "https://www.yna.co.kr/rss/economy.xml"},
]


@dag(
    dag_id="yna_collect",
    default_args=default_args,
    schedule="*/30 * * * *",
    start_date=datetime(2026, 1, 1),
    catchup=False,
    is_paused_upon_creation=False,
    tags=["collect", "yna"],
)
def yna_dag():

    @task
    def collect_politics():
        s = SOURCES[0]
        return collect_rss(s["source_id"], s["category_id"], s["rss_url"])

    @task
    def collect_economy():
        s = SOURCES[1]
        return collect_rss(s["source_id"], s["category_id"], s["rss_url"])

    collect_politics()
    collect_economy()


yna_dag()