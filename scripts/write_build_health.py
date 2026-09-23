from pathlib import Path
from datetime import datetime,timezone
import json,os
ROOT=Path(__file__).resolve().parents[1]
def main():
    payload={
      "schema_version":1,
      "generated_at":datetime.now(timezone.utc).isoformat(),
      "commit_sha":os.getenv("GITHUB_SHA"),
      "run_id":os.getenv("GITHUB_RUN_ID"),
      "run_attempt":os.getenv("GITHUB_RUN_ATTEMPT"),
      "event":os.getenv("GITHUB_EVENT_NAME"),
      "validation":{"javascript":"passed","python":"passed","repository_tests":"passed","site_health":"passed"},
      "purpose":"Deployment-time machine-readable health marker; collector freshness remains governed by .github/recovery/policy.json."
    }
    p=ROOT/"data/site_build_health.json";p.write_text(json.dumps(payload,indent=2)+"\n",encoding="utf-8")
    print(f"Wrote {p.relative_to(ROOT)}")
if __name__=="__main__": main()
