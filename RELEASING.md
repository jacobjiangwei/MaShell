# Release & Publishing Guide

## 🚀 Release Process

### 1. Update Version

Edit `pyproject.toml`:
```toml
version = "0.2.0"  # bump this
```

### 2. Commit & Tag

```bash
git add -A
git commit -m "Release v0.2.0"
git tag v0.2.0
git push origin main --tags
```

### 3. Create GitHub Release

1. Go to GitHub → Releases → "Create a new release"
2. Select your tag (v0.2.0)
3. Write release notes
4. Click "Publish release"

This automatically triggers:
- ✅ **PyPI publish** → `pip install mashell`
- ✅ **Homebrew formula update** → `brew install your-username/tap/mashell`

---

## 📦 PyPI Setup (One-time)

### Option A: Trusted Publishing (Recommended)

1. Create account at https://pypi.org
2. Go to: https://pypi.org/manage/account/publishing/
3. Add new pending publisher:
   - Project name: `mashell`
   - Owner: `your-github-username`
   - Repository: `MaShell`
   - Workflow: `publish.yml`
   - Environment: `pypi`

4. In GitHub repo, create environment:
   - Settings → Environments → New environment → Name: `pypi`

No API token needed with trusted publishing!

### Option B: API Token

1. Create token at https://pypi.org/manage/account/token/
2. Add to GitHub: Settings → Secrets → `PYPI_API_TOKEN`
3. Update `.github/workflows/publish.yml` to use token

---

## 🍺 Homebrew Setup (One-time)

### 1. Create Homebrew Tap Repository

Create a new repo: `github.com/your-username/homebrew-tap`

```bash
mkdir homebrew-tap
cd homebrew-tap
mkdir Formula
git init
git remote add origin git@github.com:your-username/homebrew-tap.git
```

### 2. Create Personal Access Token

1. GitHub → Settings → Developer settings → Personal access tokens
2. Generate new token with `repo` scope
3. Add to MaShell repo: Settings → Secrets → `HOMEBREW_TAP_TOKEN`

### 3. Users Can Then Install

```bash
brew tap your-username/tap
brew install mashell
```

---

## 📋 CI/CD Workflows

| Workflow | Trigger | What it does |
|----------|---------|--------------|
| `ci.yml` | Push/PR to main | Run tests, lint, type check |
| `publish.yml` | Push tag `v*` | Upload to PyPI |
| `homebrew.yml` | Push tag `v*` | Update Homebrew formula |

---

## 🔧 Manual Release (if needed)

```bash
# Build
pip install build
python -m build

# Upload to PyPI
pip install twine
twine upload dist/*

# Or test on TestPyPI first
twine upload --repository testpypi dist/*
pip install -i https://test.pypi.org/simple/ mashell
```
