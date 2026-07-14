# Infrastructure Deployment Log – COMP90024 Assignment 2, Team 19

## ☁️ Cloud Infrastructure Setup

This document outlines the step-by-step infrastructure deployment work completed by YiXiang Wang for Team 19's Assignment 2 project.

## ✅ Summary of Progress

- Kubernetes cluster created and verified on NeCTAR
- ElasticSearch and Kibana deployed successfully
- Fission framework installed and validated
- Fission CLI installed and functional
- Test function (`health.py`) deployed and executed correctly

## 🔧 1. Kubernetes Cluster Creation (NeCTAR)

- Logged into NeCTAR dashboard
- Downloaded OpenStack RC file and sourced credentials in terminal
- Created Kubernetes cluster:

```
openstack coe cluster create \
  --cluster-template "kubernetes-v1.31.1-melbourne-qh2-uom-v4" \
  --node-count 3 \
  --master-count 1 \
  --master-flavor "uom.mse.2c9g" \
  --flavor "uom.mse.2c9g" \
  comp90024
```

- Waited until status: `CREATE_COMPLETE` and health: `HEALTHY`

## 📦 2. ElasticSearch & Kibana Deployment

- Installed Helm:

```
brew install helm
```

- Configured storage class:

```
kubectl apply -f installation/storage-class.yaml
```

- Installed ElasticSearch:

```
export ES_VERSION="8.5.1"
helm repo add elastic https://helm.elastic.co
helm repo update
helm upgrade --install \
  --version=${ES_VERSION} \
  --create-namespace \
  --namespace elastic \
  --set replicas=2 \
  --set secret.password="elastic" \
  --set volumeClaimTemplate.resources.requests.storage="100Gi" \
  --set volumeClaimTemplate.storageClassName="perfretain" \
  elasticsearch elastic/elasticsearch
```

- Installed Kibana:

```
helm upgrade --install \
  --version=${ES_VERSION} \
  --namespace elastic \
  -f ./installation/kibana-values.yaml \
  kibana elastic/kibana
```

- Validated with:

```
kubectl get pods -n elastic
kubectl port-forward service/kibana-kibana -n elastic 5601:5601
```

Accessed Kibana at: http://localhost:5601

## ⚡ 3. Fission Deployment

- Installed Fission:

```
export FISSION_VERSION='1.21.0'
kubectl create -k "github.com/fission/fission/crds/v1?ref=v${FISSION_VERSION}"
helm repo add fission-charts "https://fission.github.io/fission-charts/"
helm repo update
helm upgrade fission fission-charts/fission-all --install \
  --version v${FISSION_VERSION} \
  --namespace fission \
  --create-namespace \
  --set routerServiceType='ClusterIP' \
  --set persistence.storageClass='perfretain'
```

- Verified deployment:

```
kubectl get pods -n fission
```

## 🔗 4. Fission CLI Installation & Validation

- Installed CLI for Mac M1 (arm64):

```
curl -Lo fission https://github.com/fission/fission/releases/download/v1.21.0/fission-v1.21.0-darwin-arm64
chmod +x fission
sudo mv fission /usr/local/bin/
```

- Verified installation:

```
fission check
```

## 🧪 5. Test Function Deployment (`health.py`)

- Created file at `functions/health.py`:

```
def main():
    return "Fission function is working!"
```

- Created Fission environment:

```
fission env create --name python --image fission/python-env --builder fission/python-builder
```

- Created and tested function:

```
fission function create --name health --env python --code ./functions/health.py
fission function test --name health
```

**Output:** `Fission function is working!`

✅ End-to-end function deployment and testing completed successfully.

## 🧭 Notes

This setup provides the foundation for deploying serverless functions, storing data in ElasticSearch, and visualising results in Kibana.

Team members can now use this environment to continue building out the core functionality, such as data harvesting, sentiment analysis, and visual dashboards.

**Prepared by:** YiXiang Wang
**Date:** 2025-05-09