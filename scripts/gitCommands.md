# Git Setup and Workflow Guide

This guide contains the recommended commands to initialize this repository, push your project to GitHub for the first time, and handle ongoing development.

---

## 🚀 1. Initial Setup (First Time Push)

> **Note:** Do NOT run `echo "# hyperlocal-marketplace" >> README.md` because a detailed 42KB `README.md` already exists in this repository.

Run these commands from the project root (`e:\hyperlocal-marketplace`):

```bash
# 1. Initialize git in the workspace
git init

# 2. Check that .gitignore is working (verify .env and .venv are ignored)
git status

# 3. Stage all files in the project
git add .

# 4. Create your initial commit
git commit -m "feat: initial commit for hyperlocal marketplace"

# 5. Ensure the branch is named main
git branch -M main

# 6. Link to your remote GitHub repository
git remote add origin https://github.com/naikamolg2003/hyperlocal-marketplace.git

# 7. Push all files and set upstream
git push -u origin main
```

---

## 🔄 2. Daily Development Workflow

Once the repository is initialized and pushed, use this routine for everyday changes:

```bash
# Check modified / untracked files
git status

# Stage changes
git add .
# OR stage specific files:
# git add <file-path>

# Commit with a clear message
git commit -m "feat: description of changes"

# Push changes to GitHub
git push
```

---

## 🛠️ 3. Troubleshooting & Useful Commands

### Check Remote URL
```bash
git remote -v
```

### Change Remote URL (if misspelled or switched to SSH)
```bash
git remote set-url origin https://github.com/naikamolg2003/hyperlocal-marketplace.git
```

### Pull Latest Changes from GitHub
```bash
git pull origin main
```

### Discard Uncommitted Local Changes
```bash
# Discard changes to a specific file
git checkout -- <filename>

# Discard all unstaged changes
git restore .
```