# Lambda Traffic Analysis — Setup & Run Guide
Replication of: *Muller et al. (2020) — A Traffic Analysis on Serverless Computing Based on a File Upload Stream on AWS Lambda*

---

## Files in this project

```
lambda-traffic-analysis/
├── handler.py            Lambda function (file upload + procfs metadata)
├── template.yaml         AWS SAM deployment template
├── traffic_generator.sh  Bash script — sends traffic in 6 interval patterns
├── download_logs.py      Downloads CloudWatch REPORT logs as CSV
├── analysis.py           Statistical analysis + plots (4 figures)
├── requirements.txt      Python dependencies
└── README.md             This file
```

---

## Prerequisites — install once

### 1. Python 3.9+
```bash
python3 --version   # must be 3.9 or newer
```

### 2. AWS CLI
```bash
pip install awscli
aws --version
```

### 3. AWS SAM CLI
```bash
pip install aws-sam-cli
sam --version
```

### 4. Python packages
```bash
pip install -r requirements.txt
```

---

## Step 1 — Configure AWS credentials

```bash
aws configure
```

You will be prompted for:
```
AWS Access Key ID     : <paste your key>
AWS Secret Access Key : <paste your secret>
Default region name   : us-east-1        ← or ap-south-1 for India (Mumbai)
Default output format : json
```

> Get your keys from AWS Console → IAM → Users → Security Credentials → Create Access Key

---

## Step 2 — Deploy Lambda functions to AWS

```bash
# From inside the lambda-traffic-analysis/ folder:
sam build
sam deploy --guided
```

During `sam deploy --guided` answer the prompts:
```
Stack Name          : lambda-traffic-analysis
AWS Region          : us-east-1           ← same region you configured above
Confirm changes     : Y
Allow SAM role      : Y
Save config file    : Y
```

When it finishes you will see output like:
```
Outputs:
  Api128Url  = https://abc123.execute-api.us-east-1.amazonaws.com/Prod/upload128
  Api512Url  = https://abc123.execute-api.us-east-1.amazonaws.com/Prod/upload512
  Api3008Url = https://abc123.execute-api.us-east-1.amazonaws.com/Prod/upload3008
```

**Copy all three URLs — you need them in Step 3.**

---

## Step 3 — Edit traffic_generator.sh

Open `traffic_generator.sh` and replace the three placeholder URLs near the top:

```bash
# Lines 22–24 — CHANGE THESE:
API_128="https://REPLACE_ME.execute-api.us-east-1.amazonaws.com/Prod/upload128"
API_512="https://REPLACE_ME.execute-api.us-east-1.amazonaws.com/Prod/upload512"
API_3008="https://REPLACE_ME.execute-api.us-east-1.amazonaws.com/Prod/upload3008"
```

Replace with your actual URLs from Step 2.

---

## Step 4 — Run traffic generation

Make the script executable, then run:

```bash
chmod +x traffic_generator.sh

# Run all 6 intervals (takes ~24 hours total):
./traffic_generator.sh

# OR run just specific intervals (faster for testing):
./traffic_generator.sh 1 2      # only intervals 1 and 2
./traffic_generator.sh 6 6      # only interval 6 (cold-start test)
```

Logs are saved automatically to `logs/traffic_log_TIMESTAMP.csv`.

---

## Step 5 — Edit download_logs.py

Open `download_logs.py` and set your region (line 16):

```python
REGION = "us-east-1"   # change to "ap-south-1" if you used Mumbai
```

Then run:
```bash
python download_logs.py
```

This saves `cloudwatch_logs.csv` in the current folder.

---

## Step 6 — Run the analysis

```bash
python analysis.py
```

This prints statistics to the terminal and saves 4 plots to `plots/`:
- `fig1_cold_start_analysis.png`  — cold vs warm boxplot + initDuration histogram
- `fig2_duration_over_time.png`   — execution duration coloured by cold/warm
- `fig3_rtt_by_interval.png`      — RTT boxplot per interval (if traffic log present)
- `fig4_coldstart_pct.png`        — cold-start as % of total duration

---

## Quick test (5 minutes, no long wait)

To verify everything is working before running the full 24-hour experiment:

```bash
# Send 5 rapid requests to the 128 MB endpoint
API="https://YOUR_URL_HERE/upload128"
for i in {1..5}; do
  curl -s -w "\nHTTP: %{http_code}  RTT: %{time_total}s\n" \
    -X POST "$API" -H "Content-Type: text/plain" --data "test $i"
done
```

You should see `HTTP: 200` for each request.

---

## Expected results (based on the paper)

| Metric                        | Expected value           |
|-------------------------------|--------------------------|
| Cold-start % of duration      | 15–17%                   |
| initDuration (cold start)     | 300–500 ms               |
| Instance idle timeout         | ~12 minutes              |
| VM automatic rotation         | ~2 hours                 |
| Memory used (128 MB config)   | ~77–79 MB                |
| Instances per VM              | Always 1 (per account)   |

---

## Cleanup (avoid AWS charges)

```bash
# Delete all deployed resources when done:
sam delete --stack-name lambda-traffic-analysis
```

This removes the Lambda functions, API Gateway, and S3 bucket.

---

## Troubleshooting

**`sam: command not found`**
```bash
pip install aws-sam-cli --user
export PATH="$HOME/.local/bin:$PATH"
```

**`curl: command not found`** (Windows)
- Use Git Bash or WSL, or replace curl with PowerShell's `Invoke-WebRequest`

**`NoCredentialsError` in Python**
- Run `aws configure` again and verify your Access Key

**CloudWatch query returns 0 rows**
- Wait 5 minutes after invoking functions before downloading logs
- Check that you used the correct region in `download_logs.py`

**S3 upload errors in the Lambda response**
- The IAM role is created automatically by SAM — wait 30 seconds after first deploy

---

## Region quick reference

| Location      | AWS Region      |
|---------------|-----------------|
| Mumbai        | ap-south-1      |
| US East (N. Virginia) | us-east-1 |
| US West (Oregon)      | us-west-2 |
| EU (Ireland)  | eu-west-1       |
| Singapore     | ap-southeast-1  |
