#!/bin/bash

echo "Deploying imikhaza to Google Cloud Run..."

# Build and deploy to Cloud Run
gcloud run deploy imikhaza \
  --source . \
  --platform managed \
  --region us-east1 \
  --allow-unauthenticated \
  --max-instances 1 \
  --memory 512Mi \
  --cpu 1 \
  --timeout 300

echo "Deployment complete!"
echo "Your app will be available at the URL shown above."
