#!/bin/bash
# =============================================================================
# ECR Push Script - Build and push Docker image to AWS ECR
# =============================================================================
# Usage: ./scripts/push_to_ecr.sh [--region REGION] [--tag TAG]
# 
# If no --tag is specified, automatically detects the latest version in ECR
# and increments it (e.g., v1 -> v2 -> v3)
#
# Prerequisites:
#   - AWS CLI configured with credentials (run 'aws configure')
#   - Docker running
#
# Loads AWS_REGION from .env file if present
# =============================================================================

set -e

# Get script directory and load .env if it exists
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ENV_FILE="$SCRIPT_DIR/../.env"

if [ -f "$ENV_FILE" ]; then
    echo "Loading configuration from .env file..."
    export $(grep -v '^#' "$ENV_FILE" | grep -v '^\s*$' | xargs)
fi

# Default values (use .env if set, otherwise defaults)
REGION="${AWS_REGION:-us-east-1}"
REPO_NAME="cg-metadata-extractor"
TAG=""  # Will be auto-detected if not specified
AUTO_VERSION=true

# Parse arguments (command line overrides .env)
while [[ $# -gt 0 ]]; do
    case $1 in
        --region)
            REGION="$2"
            shift 2
            ;;
        --tag)
            TAG="$2"
            AUTO_VERSION=false
            shift 2
            ;;
        *)
            echo "Unknown option: $1"
            exit 1
            ;;
    esac
done

# Get AWS account ID
echo "Getting AWS account ID..."
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
if [ -z "$ACCOUNT_ID" ]; then
    echo "ERROR: Could not get AWS account ID. Make sure AWS CLI is configured."
    exit 1
fi

ECR_URI="${ACCOUNT_ID}.dkr.ecr.${REGION}.amazonaws.com/${REPO_NAME}"

# Create ECR repository if it doesn't exist
echo "Ensuring ECR repository exists..."
aws ecr describe-repositories --repository-names "$REPO_NAME" --region "$REGION" 2>/dev/null || \
    aws ecr create-repository --repository-name "$REPO_NAME" --region "$REGION"

# Auto-detect next version if no tag specified
if [ "$AUTO_VERSION" = true ]; then
    echo ""
    echo "Detecting latest version from ECR..."
    
    # Get all image tags from ECR
    EXISTING_TAGS=$(aws ecr list-images --repository-name "$REPO_NAME" --region "$REGION" \
        --query 'imageIds[*].imageTag' --output text 2>/dev/null || echo "")
    
    # Find the highest version number (looking for v1, v2, v3, etc.)
    LATEST_VERSION=0
    for tag in $EXISTING_TAGS; do
        # Extract version number from tags like v1, v2, v10, etc.
        if [[ $tag =~ ^v([0-9]+)$ ]]; then
            VERSION_NUM="${BASH_REMATCH[1]}"
            if [ "$VERSION_NUM" -gt "$LATEST_VERSION" ]; then
                LATEST_VERSION=$VERSION_NUM
            fi
        fi
    done
    
    # Increment to get next version
    NEXT_VERSION=$((LATEST_VERSION + 1))
    TAG="v${NEXT_VERSION}"
    
    if [ "$LATEST_VERSION" -eq 0 ]; then
        echo "No existing versions found. Starting at v1"
    else
        echo "Latest version: v${LATEST_VERSION}"
        echo "Next version:   ${TAG}"
    fi
fi

echo ""
echo "============================================="
echo "ECR Push Configuration"
echo "============================================="
echo "Account ID:  $ACCOUNT_ID"
echo "Region:      $REGION"
echo "Repository:  $REPO_NAME"
echo "Tag:         $TAG"
echo "ECR URI:     $ECR_URI:$TAG"
echo "============================================="
echo ""

# Authenticate Docker to ECR
echo "Authenticating Docker to ECR..."
aws ecr get-login-password --region "$REGION" | docker login --username AWS --password-stdin "${ACCOUNT_ID}.dkr.ecr.${REGION}.amazonaws.com"

# Build the Docker image
echo ""
echo "Building Docker image..."
docker build -t "$REPO_NAME:$TAG" .

# Tag for ECR (versioned tag)
echo ""
echo "Tagging image for ECR..."
docker tag "$REPO_NAME:$TAG" "$ECR_URI:$TAG"

# Also tag as 'latest' for convenience
docker tag "$REPO_NAME:$TAG" "$ECR_URI:latest"

# Push to ECR (both tags)
echo ""
echo "Pushing to ECR..."
docker push "$ECR_URI:$TAG"
echo "Pushing 'latest' tag..."
docker push "$ECR_URI:latest"

echo ""
echo "============================================="
echo "SUCCESS! Image pushed to ECR"
echo "============================================="
echo "Versioned URI: $ECR_URI:$TAG"
echo "Latest URI:    $ECR_URI:latest"
echo ""
echo "Use the versioned URI in your AWS Batch job definition"
echo "for reproducible deployments."
