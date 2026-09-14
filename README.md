# 🎯 Tavor Skill - Automated Code Review Agent

AI-powered code review agent that runs on every GitLab merge request. Reviews code against **Tavor Code Review Conventions** (team standards for Angular 19 frontend + NestJS backend).

## ✨ Features

- **Automated Reviews**: Runs on every MR automatically via GitLab CI/CD
- **Convention Enforcement**: Reviews against Tavor team conventions (SOLID principles, logging, type safety, etc.)
- **Structured Feedback**: 
  - 🛑 **Critical Issues** (blockers)
  - ⚠️ **Major Issues** (warnings)
  - 💡 **Suggestions** (nice to have)
- **Scoring**: 1-10 score for code quality
- **Decision**: APPROVE, REQUEST_CHANGES, or COMMENT
- **Local Claude Support**: Works with air-gapped/local Claude instances
- **GitLab Native**: Posts reviews as native MR comments

## 📋 Tavor Conventions Covered

### Backend (NestJS 11+)
- ✅ SOLID principles (SRP, OCP)
- ✅ Controller → Service → Repository pattern
- ✅ Swagger documentation on every endpoint
- ✅ Type safety (zero "any" types)
- ✅ Logging (INFO/ERROR with correlation IDs)
- ✅ Database query optimization
- ✅ Dependency injection best practices

### Frontend (Angular 19)
- ✅ Atomic Design pattern
- ✅ Signal-based reactivity
- ✅ LoggerService for user interactions
- ✅ Type safety (zero "any" types)
- ✅ Component file structure (separate .ts, .html, .scss)
- ✅ SCSS nesting and styling patterns
- ✅ No hardcoded strings or magic numbers

### General
- ✅ Git workflow (branch naming, commit messages)
- ✅ No deprecated packages
- ✅ Database migrations (naming, rollback strategy)
- ✅ Error handling (HTTP status codes)

## 🚀 Quick Start

### 1. Setup Repository

```bash
# Clone your repo (or add these files if repo exists)
git clone https://github.com/liorpoleg/tavor-skill.git
cd tavor-skill

# Files are already created:
# - .gitlab-ci.yml        (GitLab CI/CD pipeline)
# - scripts/code-review.py (review agent)
# - README.md             (this file)
```

### 2. Configure GitLab

Add these environment variables to your GitLab project:

**Settings → CI/CD → Variables**

```
LLM_ENDPOINT = https://api.anthropic.com
LLM_MODEL = claude-opus-4-1-20250805
LLM_API_KEY = sk-ant-xxx...
GITLAB_TOKEN = your_gitlab_personal_access_token
```

**Supported LLM Providers:**
- Anthropic API: `https://api.anthropic.com`
- Local Claude: `http://localhost:8000`
- Any compatible LLM endpoint

**Generate GitLab Token:**
- Go to: GitLab → Settings (top-right) → Access Tokens
- Create token with scope: `api`, `read_api`, `write_repository`
- Copy the token value

### 3. Push to GitLab

```bash
git add .gitlab-ci.yml scripts/ README.md
git commit -m "feat: add Tavor automated code review agent"
git push origin main
```

### 4. Test on a Merge Request

Create a test MR:
```bash
git checkout -b test/review-agent
echo "test" > test.txt
git add test.txt
git commit -m "test: verify review agent"
git push origin test/review-agent
```

Go to GitLab UI → Create Merge Request → Watch pipeline run → See review comment appear! ✨

## 📖 How It Works

### Workflow

```
Developer pushes to branch
    ↓
GitLab detects merge request
    ↓
CI/CD pipeline triggered (via .gitlab-ci.yml)
    ↓
Python script runs:
  1. Fetches code diff
  2. Calls Claude API with Tavor skill
  3. Claude analyzes code against conventions
  4. Posts review as MR comment
    ↓
Developer sees review on the MR
```

### Example Review Output

```
✅ Automated Code Review by Tavor

Score: 8/10
Decision: ✅ APPROVE - Ready to merge

### Summary
Added user authentication endpoint with password hashing.
Good separation of concerns, clean controller/service split.

### 🛑 CRITICAL Issues (Blockers - Must Fix)
None

### ⚠️ MAJOR Issues (Warnings - Should Fix)
1. src/users/users.controller.ts:45
   Missing @ApiResponse decorator for 401 Unauthorized
   💡 Convention: Every endpoint must have @ApiResponse for all status codes

### 💡 SUGGESTIONS (Nice to Have)
1. src/users/users.service.ts - Consider adding INFO log when password reset succeeds
2. src/users/dto/create-user.dto.ts - @IsOptional() recommended for optional fields

### Decision Reason
Code follows SRP, has good error handling, and includes Swagger documentation.
Minor suggestion to add more logging for audit trail.

---
🤖 Review by Tavor Conventions
```

## 🔧 Configuration

### Environment Variables

| Variable | Required | Example | Description |
|----------|----------|---------|-------------|
| `LLM_ENDPOINT` | ✅ | `https://api.anthropic.com` | LLM API endpoint |
| `LLM_MODEL` | ✅ | `claude-opus-4-1-20250805` | Model name |
| `LLM_API_KEY` | ✅ | `sk-ant-xxx...` | LLM API authentication key |
| `GITLAB_TOKEN` | ✅ | `glpat-xxx...` | GitLab personal access token |
| `CI_PROJECT_ID` | ✅ | `123` | Set by GitLab automatically |
| `CI_MERGE_REQUEST_IID` | ✅ | `456` | Set by GitLab automatically |
| `CI_SERVER_URL` | ✅ | `https://gitlab.example.com` | Your GitLab URL |

### Customize Review Rules

Edit `scripts/code-review.py` and modify the `TAVOR_SKILL` constant to adjust which conventions to enforce.

### Run Locally (for testing)

```bash
# Install dependencies
pip install requests python-dotenv

# Set environment variables
export LLM_ENDPOINT="https://api.anthropic.com"
export LLM_MODEL="claude-opus-4-1-20250805"
export LLM_API_KEY="sk-ant-xxx..."
export GITLAB_TOKEN="your_token"
export CI_PROJECT_ID="123"
export CI_MERGE_REQUEST_IID="456"
export CI_SERVER_URL="https://gitlab.example.com"

# Run the script
python scripts/code-review.py
```

## 🛑 Blocking Merges with Critical Issues

To automatically block merges when critical issues are found, uncomment this in `.gitlab-ci.yml`:

```yaml
code-review-gate:
  stage: review
  image: python:3.11
  script:
    # ... check review_result.json for critical issues
    # ... exit 1 if found (blocks merge)
  allow_failure: false  # Block merge if job fails
```

Or add GitLab branch protection rule:
- Settings → Repository → Protected Branches
- Require all CI/CD jobs to pass before merge

## 📊 Review Decision Guide

### ✅ APPROVE
- No critical or major issues
- Code follows conventions
- Ready to merge immediately

### ⚠️ REQUEST_CHANGES
- Has critical issues (blockers)
- Code review comments require action
- Developer must fix and push again

### 💬 COMMENT
- Only minor suggestions
- No blockers, ready to merge if developer wants
- Comments are informational

## 🐛 Troubleshooting

### "Could not connect to Claude API"
- Verify Claude is running: `curl http://your-api:8000/health`
- Check `CLAUDE_API_URL` is correct in GitLab Variables
- Verify network/firewall allows connection

### "GITLAB_TOKEN invalid"
- Generate new token: GitLab → Settings → Access Tokens
- Requires scopes: `api`, `read_api`, `write_repository`
- Update in GitLab Variables

### Review not posting to MR
- Check `CI_PROJECT_ID` and `CI_MERGE_REQUEST_IID` are set
- Verify token has `write_repository` scope
- Check GitLab project visibility (token needs access)

### JSON parsing error from Claude
- Verify Claude is responding with valid JSON
- Check Claude API is version `claude-opus-4.5` or later
- Increase `max_tokens` in script if response is truncated

## 🎓 Integration Examples

### With GitHub Actions (if using GitHub)
Use `.github/workflows/code-review.yml` instead:
```yaml
name: Code Review
on: [pull_request]
jobs:
  review:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - run: python scripts/code-review.py
        env:
          CLAUDE_API_URL: ${{ secrets.CLAUDE_API_URL }}
          CLAUDE_API_KEY: ${{ secrets.CLAUDE_API_KEY }}
```

### With Pre-commit Hook (local)
```bash
#!/bin/bash
# .git/hooks/pre-commit
python scripts/code-review.py --local
```

### With Custom Slack Notifications
Add to `code-review.py`:
```python
def post_to_slack(self, review: Dict[str, Any]) -> None:
    """Optional: Send review summary to Slack"""
    webhook_url = os.getenv("SLACK_WEBHOOK_URL")
    if not webhook_url:
        return
    
    # Post to Slack channel
```

## 📚 Tavor Conventions Reference

For full documentation of Tavor conventions, see:
- **Notion Skill**: https://app.notion.com/p/3da464a25ed5810aa5adfd3df27ca806
- **Full Details**: [CONVENTIONS.md](./CONVENTIONS.md) *(optional, can add later)*

## 🤝 Contributing

To improve Tavor code review:

1. Update `TAVOR_SKILL` in `scripts/code-review.py`
2. Test on a test MR
3. Commit changes: `git commit -m "docs: update Tavor conventions"`
4. Push: `git push origin main`

## 📞 Support

**Questions about setup?**
- Check `.gitlab-ci.yml` pipeline logs in GitLab
- Review script output: `python scripts/code-review.py --help`
- Check Claude API health: `curl http://your-api:8000/health`

**Want to customize reviews?**
- Edit `TAVOR_SKILL` in `scripts/code-review.py`
- Modify Claude prompt to emphasize different conventions
- Add backend/frontend-specific review logic

## 📄 License

Tavor Skill is an internal tool for team code reviews.

---

**Made with 🤖 Claude** | **Team: Tavor** | **Last Updated: 2026-09-13**
