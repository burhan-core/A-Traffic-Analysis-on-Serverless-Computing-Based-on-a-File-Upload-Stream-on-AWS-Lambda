# Lambda Traffic Analysis on AWS

A replication of the research paper:
> *Muller et al. (2020) — A Traffic Analysis on Serverless Computing Based on a File Upload Stream on AWS Lambda*

---

## What This Project Does

Deploys a File Upload function on AWS Lambda and measures:
- **Cold-Start latency** — extra delay when a new container spins up
- **Round-Trip Time** — total request to response time
- **Auto-scaling behaviour** — how AWS distributes load across VMs
- **VM lifetime & idle timeout** — when instances go cold

---

## Project Files

```
lambda-traffic-analysis/
├── src/
│   └── handler.py            # Lambda function (file upload + metadata collector)
├── template.yaml             # AWS SAM deployment config
├── traffic_generator.sh      # Sends traffic in 6 interval patterns (Linux/Mac)
├── download_logs.py          # Downloads CloudWatch logs as CSV
├── analysis.py               # Generates stats + 4 plots
└── requirements.txt          # Python packages for analysis
```

---

## Requirements

- Python 3.9+
- AWS account (free tier works)
- AWS CLI — `pip install awscli`
- AWS SAM CLI — `pip install aws-sam-cli`
- Analysis packages — `pip install -r requirements.txt`

---

## Setup & Run

### 1. Configure AWS
```bash
aws configure
# Enter your Access Key, Secret Key, region (e.g. ap-south-1), and json
```

### 2. Deploy to AWS
```bash
sam build
sam deploy --guided
# Note the 3 API URLs printed at the end
```

### 3. Edit traffic_generator.sh
Open the file and replace the 3 URLs at lines 22–24 with your actual API URLs from Step 2.

### 4. Run traffic (Linux/Mac)
```bash
chmod +x traffic_generator.sh
./traffic_generator.sh 1 2      # quick test (~30 min)
./traffic_generator.sh          # full 24-hour run
```

### 4. Run traffic (Windows PowerShell)
```powershell
$API = "https://YOUR_URL/Prod/upload128"
for ($i = 1; $i -le 10; $i++) {
    Invoke-WebRequest -Uri $API -Method POST -Body "test $i" -ContentType "text/plain"
    Start-Sleep -Seconds 30
}
```

### 5. Download logs
```bash
python download_logs.py
# Edit REGION inside the file first (e.g. "ap-south-1")
```

### 6. Analyse results
```bash
python analysis.py
# Prints stats and saves 4 plots in /plots
```

### 7. Cleanup
```bash
sam delete --stack-name sam-app
```

---

## Expected Results

| Metric | Expected Value |
|---|---|
| Cold-Start % of RTT | 15–17% |
| Instance idle timeout | ~12 minutes |
| VM automatic rotation | ~2 hours |
| Instances per VM | Always 1 |
| Memory used (128 MB config) | ~77–79 MB |

---

## Troubleshooting

**`sam build` fails with python version error**
Change `Runtime: python3.9` to `Runtime: python3.12` in `template.yaml`

**`AccessDenied` during deploy**
Go to AWS Console → IAM → Users → your user → Add permissions → attach `AdministratorAccess`

**`sam delete` not working**
Use the exact stack name from your deploy: `sam delete --stack-name sam-app`

**CloudWatch returns 0 rows**
Wait 5 minutes after invoking functions, and confirm `REGION` in `download_logs.py` matches your deploy region
