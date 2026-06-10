from airflow.sdk import dag, task
from datetime import datetime, timedelta
from common import collect_rss_sbs

default_args = {
    'owner': 'airflow',
    'retries': 2,
    'retry_delay': timedelta(minutes=5),
}

SOURCES = [
    {"source_id": 11, "category_id": 1, "rss_url": "https://news.sbs.co.kr/news/SectionRssFeed.do?sectionId=01"},
    {"source_id": 12, "category_id": 2, "rss_url": "https://news.sbs.co.kr/news/SectionRssFeed.do?sectionId=02"},
]


@dag(
    dag_id="sbs_collect",
    default_args=default_args,
    schedule="*/30 * * * *",
    start_date=datetime(2026, 1, 1),
    catchup=False,
    is_paused_upon_creation=False,
    tags=["collect", "sbs"],
)
def sbs_dag():

    @task
    def collect_politics():
        s = SOURCES[0]
        return collect_rss_sbs(s["source_id"], s["category_id"], s["rss_url"])

    @task
    def collect_economy():
        s = SOURCES[1]
        return collect_rss_sbs(s["source_id"], s["category_id"], s["rss_url"])

    collect_politics()
    collect_economy()


sbs_dag()