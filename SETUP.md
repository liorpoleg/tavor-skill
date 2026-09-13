# 🚀 Tavor Setup Guide

Get Tavor automated code review running in 5 minutes.

## Step 1: Generate GitLab Personal Access Token

1. Go to GitLab: **Settings (⚙️ top-right) → Access Tokens**
2. Create token:
   - **Token name**: `tavor-code-review`
   - **Scopes**: Check `api`, `read_api`, `write_repository`
   - **Expiration**: Optional (90 days default)
3. Copy the token (you'll need it in Step 3)

**Example:**
```
glpat-abcd1234efgh5678ijkl
```

## Step 2: Setup GitLab Project Variables

1. Go to your GitLab project
2. **Settings → CI/CD → Variables**
3. Add these 3 variables (click **Add variable** for each):

| Key | Value | Protected | Masked |
|-----|-------|-----------|--------|
| `CLAUDE_API_URL` | `http://your-claude-server:8000` | ✅ | ✅ |
| `CLAUDE_API_KEY` | `your-claude-api-key` | ✅ | ✅ |
| `GITLAB_TOKEN` | `glpat-xxx...` (from Step 1) | ✅ | ✅ |

**For air-gapped local Claude:**
```
CLAUDE_API_URL = http://localhost:8000
```

**For cloud Claude (Anthropic API):**
```
CLAUDE_API_URL = https://api.anthropic.com
CLAUDE_API_KEY = sk-ant-xxx...
```

## Step 3: Add Files to Your Repository

If you haven't cloned yet:
```bash
git clone https://github.com/liorpoleg/tavor-skill.git your-project
cd your-project
```

These files are already in the repo:
- `.gitlab-ci.yml` - Pipeline configuration
- `scripts/code-review.py` - Review agent
- `README.md` - Full documentation

Copy them to your project if needed:
```bash
cp .gitlab-ci.yml /path/to/your/project/
cp -r scripts/ /path/to/your/project/
```

## Step 4: Push to GitLab

```bash
cd /path/to/your/project
git add .gitlab-ci.yml scripts/code-review.py
git commit -m "feat: add Tavor automated code review"
git push origin main
```

## Step 5: Test It! 🎉

Create a test merge request:

```bash
# Create a test branch
git checkout -b test/tavor-review

# Make a small change
echo "# Test" >> README.md

# Commit and push
git add README.md
git commit -m "test: verify Tavor code review"
git push origin test/tavor-review
```

Then:
1. Go to GitLab UI
2. Create Merge Request
3. Watch the CI/CD pipeline run
4. See the Tavor review comment appear! 🤖

## ✅ Verification Checklist

- [ ] GitLab token created with correct scopes
- [ ] 3 variables added to GitLab project settings
- [ ] `.gitlab-ci.yml` added to repository root
- [ ] `scripts/code-review.py` added to repository
- [ ] Files committed and pushed to GitLab
- [ ] Test MR created
- [ ] Pipeline ran successfully
- [ ] Review comment posted to MR

## 🐛 Quick Troubleshooting

**Pipeline fails with "connection refused"**
- ❌ Claude API not running or wrong URL
- ✅ Fix: Check `CLAUDE_API_URL` in GitLab variables
- ✅ Fix: Verify Claude is running: `curl http://your-api:8000/health`

**Pipeline fails with "token invalid"**
- ❌ GitLab token missing `write_repository` scope
- ✅ Fix: Regenerate token with correct scopes
- ✅ Fix: Update `GITLAB_TOKEN` in variables

**Review not posted to MR**
- ❌ Token doesn't have project access
- ✅ Fix: Verify token can access your GitLab instance
- ✅ Fix: Check project is not private (if using limited token)

**No review comment shows up**
- ❌ Pipeline succeeded but Claude returned error
- ✅ Fix: Check GitLab CI/CD job logs for Claude error
- ✅ Fix: Verify code diff is not too large (>15KB)

## 🎓 Next Steps

1. **Customize conventions**: Edit `TAVOR_SKILL` in `scripts/code-review.py`
2. **Block merges on critical issues**: Uncomment `code-review-gate` in `.gitlab-ci.yml`
3. **Add to branch protection**: Settings → Repository → Protected Branches
4. **Team onboarding**: Share Tavor Notion skill with team

## 📞 Support

**Need help?**
- Read full docs: `README.md`
- Check script logs: GitLab → Pipelines → [Your pipeline] → Jobs
- View Tavor skill: https://app.notion.com/p/3da464a25ed5810aa5adfd3df27ca806

---

**You're all set! 🚀 Tavor will now review every MR automatically.**
