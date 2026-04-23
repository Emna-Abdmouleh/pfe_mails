import schedule
import time
from pipeline_auto import run_pipeline

def job():
    run_pipeline()

# Lance immédiatement puis toutes les 5 minutes
job()
schedule.every(5).minutes.do(job)

print("Scheduler démarré — Ctrl+C pour arrêter")
while True:
    schedule.run_pending()
    time.sleep(30)