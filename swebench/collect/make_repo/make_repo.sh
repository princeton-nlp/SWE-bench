#!/usr/bin/env bash

# Mirror repository to https://github.com/swe-bench
# Usage make_repo.sh {gh organization}/{gh repository}

# Abort on error
set -euo pipefail

REPO_TARGET=$1

# Check if the target repository exists
gh repo view "$REPO_TARGET" > /dev/null || exit 1

# Set the organization and repository names
ORG_NAME="vinhowe"
NEW_REPO_NAME="${REPO_TARGET//\//__}"
DEFAULT_BRANCH=$(gh api "repos/$REPO_TARGET" --jq .default_branch)
echo "Default branch of $REPO_TARGET is $DEFAULT_BRANCH"

# Check if the new repository already exists
if gh repo view "$ORG_NAME/$NEW_REPO_NAME" > /dev/null 2>&1; then
    echo "The repository $ORG_NAME/$NEW_REPO_NAME already exists."
else
    # Create mirror repository
    # gh repo create "$ORG_NAME/$NEW_REPO_NAME" --private
    gh repo create "$ORG_NAME/$NEW_REPO_NAME" --public
fi

# Check if the repository creation was successful
if [ $? -eq 0 ]; then
    echo "** Repository created successfully at $ORG_NAME/$NEW_REPO_NAME."
else
    echo "Failed to create the repository."
    exit 1
fi

# Clone the target repository
echo "** Cloning $REPO_TARGET..."
TARGET_REPO_DIR="${REPO_TARGET##*/}.git"

# Check if the local repository directory already exists
if [ -d "$TARGET_REPO_DIR" ]; then
    echo "The local repository directory $TARGET_REPO_DIR already exists."
    exit 1
fi

git clone --bare git@github.com:$REPO_TARGET.git

# Push files to the mirror repository
echo "** Performing mirror push of files to $ORG_NAME/$NEW_REPO_NAME..."
cd "$TARGET_REPO_DIR"; git push --mirror git@github.com:$ORG_NAME/$NEW_REPO_NAME

# Remove the target repository
cd ..; rm -rf "$TARGET_REPO_DIR"

# Clone the mirror repository
git clone git@github.com:$ORG_NAME/$NEW_REPO_NAME.git

# Delete .github/workflows if it exists
if [ -d "$NEW_REPO_NAME/.github/workflows" ]; then
    git checkout "$DEFAULT_BRANCH"

    # Remove the directory
    rm -rf "$NEW_REPO_NAME/.github/workflows"

    # Commit and push the changes
    cd "$NEW_REPO_NAME";
    git add -A;
    git commit -m "Removed .github/workflows";
    git push origin "$DEFAULT_BRANCH";
    cd ..;
else
    echo "$NEW_REPO_NAME/.github/workflows does not exist. No action required."
fi

rm -rf "$NEW_REPO_NAME"
