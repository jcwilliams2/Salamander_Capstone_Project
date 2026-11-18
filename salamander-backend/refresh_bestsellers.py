import sys
import time
from bestsellers import NYT_LISTS, NYT_PAUSE_SECONDS, fetch_list, ingest_bestsellers
from bestseller_cache import write_rankings

def _safe(e):
    return str(e) if isinstance(e, RuntimeError) else type(e).__name__

def refresh(lists=NYT_LISTS, fetch=fetch_list, ingest=ingest_bestsellers, write=write_rankings,
            pause=NYT_PAUSE_SECONDS, sleep=time.sleep):
    report = {"fetched": [], "failed": [], "written": {}, "ingest": None, "ok": False}
    fetched =[]
    for i, name in enumerate(lists):
        if i:
            sleep(pause)
        try:
            fetched.append(fetch(name))
        except Exception as e:
            print(f" Could not fetch {name}: {_safe(e)}")
            report["failed"].append(name)
    if not fetched:
        return report
    try:
        result = ingest(fetched)
    except Exception as e:
        print(f" Ingestion failed: {_safe(e)}")
        report["failed"] += [l["list_name"] for l in fetched]
        return report
    report["ingest"] = result["summary"]
    for lst in result["lists"]:
        try:
            report["written"][lst["list_name"]] = write(lst)
            report["fetched"].append(lst["list_name"])
        except Exception as e:
            print(f" Could not save {lst['list_name']}: {_safe(e)}")
            report["failed"].append(lst["list_name"])
    report["ok"] = not report["failed"]
    return report


def main():
    report = refresh()
    print(report)
    return 0 if report["ok"] else 1

if __name__ == "__main__":
    sys.exit(main())