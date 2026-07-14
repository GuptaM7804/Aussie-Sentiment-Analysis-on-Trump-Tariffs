# COMP90024 - Cluster and Cloud Computing Assignment 2 Group 19

## 🧠 Project Topic: What do Australians think of Donald Trump and the use of tariffs across the different social media platforms?

This project analyzes Australians sentiment on Donald Trump and tariffs using Reddit and Mastodon data.  
Our objectives are to:

- Harvest data via Fission-deployed functions
- Store and index posts in Elasticsearch
- Analyze sentiment and keyword frequency using Jupyter Notebooks
- Compare sentiment trends across platforms

---

## 📁 Folder Structure

### `/frontend/` – Jupyter-based analysis environment

- `sentiment-analysis.ipynb`: main analysis notebook (deployed to Jupyter in Kubernetes)
- `analysis_utils.py`: helper functions for querying and processing ES data
- `requirements-jupyter.txt`: dependencies for analysis environment
- `Dockerfile`: Docker image for cloud-based Jupyter Notebook
- `deployment.yaml` / `service.yaml`: Kubernetes specs for Jupyter deployment

### `/backend/` – Data harvesting and ingestion

- `harvest.py`: collects Reddit/Mastodon data
- `keywords.json`: keywords used in data search

### `/database/` – Elasticsearch index configuration

- `create_index_reddit.json`: Reddit index schema
- `create_index_mastodon.json`: Mastodon index schema
- `search_tarrifs.json`: sample query
- `*.json` + `*.sh`: Elasticsearch index creation scripts

### `/Kubernetes/` – Fission-based data harvesting specs

- `cronjob.yaml`: scheduled harvester CronJob
- `secret.yaml.example`: template for API keys used by Fission functions (copy to `secret.yaml` and fill in your own values locally — the real file is never committed)

### `/deployment/` – Cluster & Fission setup

- `cluster-setup.md`: notes for deploying to Kubernetes + Fission on Nectar

### `/config/` – Local configuration

- Non-secret configuration used during development/deployment. Any files containing credentials or environment-specific values are excluded from version control (see `.gitignore`).

### `/data/` – Sample/mock data

- `reddit_data_sample.json`, `processed_data.json`, etc.
- Note: this contains sample/mock data only for demonstrating the pipeline. Any larger harvested datasets are excluded from the repository.

### `/test/` – Testing scripts

- Include logic tests for sentiment scoring, ES connectivity, etc.

### `/docs/` – Reports & team planning

- `task-ownership.md`: who did what
- `data-plan.md`: harvesting plan
- Work logs for individual members

---

## 🚀 Deployment Overview

Our system is deployed entirely on the Nectar Research Cloud using Kubernetes and Fission.

### 1. Elasticsearch & Kibana
- Deployed via Helm chart into the Kubernetes cluster.
- Exposed via port-forward (`kubectl port-forward`) for secure access.
- Indexes created via custom JSON schema under `/database/`.

### 2. Fission + CronJobs for Harvester
- Harvester logic (`harvest.py`) is packaged as Fission functions.
- Kubernetes CronJobs are defined to schedule harvesting every hour.
- Environment variables and API keys are securely injected via Kubernetes Secrets (see `Kubernetes/secret.yaml.example` for the required format — never commit the real file).

### 3. Data Ingestion Workflow
- Harvested Reddit and Mastodon posts are uploaded immediately to Elasticsearch using unique IDs.

### 4. Jupyter Notebook for Analysis
- A custom Docker image (`frontend/Dockerfile`) based on `jupyter/base-notebook` includes:
  - `sentiment-analysis.ipynb`
  - `analysis_utils.py`
  - Required Python libraries (`requirements-jupyter.txt`)
- Deployed to Kubernetes using `frontend/deployment.yaml` and exposed via `kubectl port-forward`.
- The notebook queries Elasticsearch directly and performs sentiment aggregation, time-series breakdowns.

---

## ✅ Tools Used

- **Fission** for serverless function deployment  
- **Elasticsearch** for full-text indexing and sentiment data storage  
- **Kubernetes** for container orchestration  
- **JupyterLab** for interactive data analysis  
- **DockerHub** for storing Docker images  
- **Python + Pandas / Seaborn / TextBlob / VADER** for sentiment processing

---

## 🔒 Access

- Jupyter is exposed via `kubectl port-forward deployment/jupyter-notebook 8888:8888` .

------

## 🧪 Reproduction Instructions

To reproduce our cloud-based social media sentiment analysis system, follow the steps below:

### 🔧 Prerequisites

- Docker installed and configured for `linux/amd64` builds
- Access to a Nectar Cloud Kubernetes cluster with `kubectl` configured
- A DockerHub account to push your custom Jupyter image

### 1. Clone the repository

```bash
git clone https://github.com/<your-repo-path>/comp90024_team_19.git
cd comp90024_team_19
```

### 2. Deploy Elasticsearch & Kibana (manual YAML method)

We use official Elasticsearch and Kibana container images, deployed manually via Kubernetes YAML files.

Apply the manifests stored in the `/Kubernetes/` folder:

```bash
kubectl apply -f Kubernetes/elasticsearch.yaml
kubectl apply -f Kubernetes/kibana.yaml
```

Then wait for the Pods to be Running:

```
kubectl get pods -n elastic
```

Once ready, forward the ports to access services locally:

```
kubectl port-forward -n elastic pod/elasticsearch-master-0 9200:9200
kubectl port-forward -n elastic service/kibana-kibana 5601:5601
```

- Access Elasticsearch at: https://localhost:9200
- Access Kibana at: http://localhost:5601

### **3. Create Elasticsearch indices**

```
cd database
bash create_index_reddit.sh
bash create_index_mastodon.sh
```

### **4. Deploy Harvester with Fission and CronJob**

- Copy `Kubernetes/secret.yaml.example` to `Kubernetes/secret.yaml`, fill in your own API keys, then apply it as a Kubernetes Secret (this file is gitignored and must be created locally):

```bash
cp Kubernetes/secret.yaml.example Kubernetes/secret.yaml
# edit Kubernetes/secret.yaml with your own credentials
kubectl apply -f Kubernetes/secret.yaml
```

- Deploy the Fission functions for harvest.py

- Apply scheduled harvester via CronJob:

```
kubectl apply -f Kubernetes/cronjob.yaml
```

- The CronJob runs your Fission function every hour to continuously fetch and upload new Reddit and Mastodon posts.

### **5. Build and Deploy Jupyter Notebook**

```
cd frontend
docker build --platform=linux/amd64 -t <your-dockerhub-username>/jupyter-notebook:latest .
docker push <your-dockerhub-username>/jupyter-notebook:latest
```

Update frontend/deployment.yaml to use your Docker image, then deploy:

```
kubectl apply -f frontend/deployment.yaml
kubectl apply -f frontend/service.yaml
```

Forward Jupyter to local port:

```
kubectl port-forward deployment/jupyter-notebook 8888:8888
```

Then access it at: http://localhost:8888

### **6. Run Sentiment Analysis**

Open sentiment-analysis.ipynb in Jupyter Notebook.

- It will connect to your in-cluster Elasticsearch
- Query posts, compute sentiment, and visualize trends
- All helper functions are in analysis_utils.py
