# Demo Evidence Output

Run:

```powershell
python -m scripts.capture_demo_evidence --run-verification --run-full-tests --run-docker-build
```

Generated command outputs, health/readiness JSON, Docker status, and evidence
manifests are stored in a date-stamped subfolder. Review all files for secrets
or identifiable data before sharing.
