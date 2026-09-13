#!/usr/bin/env python3
"""
Tavor Automated Code Review Agent
Runs on every GitLab merge request to review code against team conventions

Usage:
  CLAUDE_API_URL=http://localhost:8000 \
  CLAUDE_API_KEY=your_key \
  GITLAB_TOKEN=your_token \
  CI_PROJECT_ID=123 \
  CI_MERGE_REQUEST_IID=456 \
  CI_SERVER_URL=https://gitlab.example.com \
  python scripts/code-review.py
"""

import os
import sys
import requests
import json
import re
from typing import Optional, List, Dict, Any


# Configuration from environment
CLAUDE_API_URL = os.getenv("CLAUDE_API_URL", "http://localhost:8000")
CLAUDE_API_KEY = os.getenv("CLAUDE_API_KEY")
GITLAB_URL = os.getenv("CI_SERVER_URL", "https://gitlab.example.com")
GITLAB_TOKEN = os.getenv("GITLAB_TOKEN")
PROJECT_ID = os.getenv("CI_PROJECT_ID")
MR_IID = os.getenv("CI_MERGE_REQUEST_IID")

# Tavor Skill - Team conventions for code review
TAVOR_SKILL = """# Tavor Code Review Conventions

## 🎯 CRITICAL: SOLID Principles

### Single Responsibility Principle (SRP)
- **One reason to change**: Each class/service should handle exactly one business concern
- **Red flag**: If you can describe a class's job using "and", it violates SRP

### Open/Closed Principle (OCP)
- **Open for extension, closed for modification**: Design services so new features extend them without modifying existing code
- **CRITICAL**: Before adding a new feature, SEARCH codebase for similar functionality
- If found: Refactor into generic, reusable service instead of duplicating

## Backend (NestJS 11+)

### Architecture: Controller → Service → Repository
- **Controllers**: Route handling + validation ONLY (no business logic)
- **Services**: Business logic + orchestration ONLY
- **Repositories**: Data access ONLY

### DTOs & Swagger (MANDATORY on EVERY endpoint)
- EVERY DTO field MUST have `@ApiProperty()` with description and example
- EVERY endpoint MUST have `@ApiOperation()`, `@ApiResponse()`, `@ApiBody()`
- Use `class-validator` decorators: `@IsEmail()`, `@IsString()`, etc.
- Typing: NEVER `any` - 100% explicit types required

### Logging (Winston to Elasticsearch)
- **INFO**: Operation boundaries (start, success, state changes)
- **ERROR**: Exceptions with full stack traces
- Include: timestamp, userId, correlationId, context
- **NEVER log**: Passwords, tokens, API keys, PII
- Structured JSON with consistent field names

### Database Queries
- **MongoDB**: `$match` BEFORE `$lookup`, `$group`, `$sort` (CRITICAL)
- **PostgreSQL**: Use `EXPLAIN ANALYZE` to verify query plans
- **All databases**: Indexes on foreign keys, no N+1 queries
- Pagination: Always use `LIMIT`/`OFFSET`

### Type Safety
- **ZERO "any" types** - 100% explicit typing required
- Check for duplicated types - unify to base type or generic
- Function parameters, return types, DTO properties all typed

### Code Simplicity
- Refactor if: >30 lines, >3 nesting levels, hard to explain
- Use built-in methods: `.map()`, `.filter()`, `.reduce()` (no loops)
- All `if` statements must have braces `{}`

## Frontend (Angular 19)

### Component Structure
- **Atomic Design**: Atoms (basic UI), Molecules (combinations), Organisms (business logic)
- **3 files always**: .ts, .html, .scss (separate, no inline)
- **Standalone components** with Signal-based inputs/outputs: `input()`, `output()`
- `effect()` for reactivity (not `ngOnChanges`)

### LoggerService (CRITICAL)
- **Log ALL user interactions**: Navigation, clicks, submissions, errors
- Sent to server for Elasticsearch persistence
- **INFO** (user actions), **ERROR** (exceptions), **WARN** (issues)
- Include correlation IDs
- **NEVER log**: Passwords, tokens, PII

### Type Safety & Naming
- **ZERO "any" types** - strict TypeScript required
- Signals prefix with `$` (e.g., `$count`, `_$internal`)
- Booleans prefix with `is` or `has` (e.g., `isActive`, `hasError`)
- Private members prefix with `_`
- File names: kebab-case
- Constants: UPPER_SNAKE_CASE

### Styling (SCSS)
- Nesting must match HTML structure
- No global styles (except scrollbars, variables)
- CSS variables for dynamic values, not class selectors
- No `!important`

## Code Quality (Both Frontend & Backend)

### No Magic Numbers or Hardcoded Strings
- All constants in `consts/` files (e.g., `user.consts.ts`)
- All user-facing text in translation maps (e.g., `*.label-map.ts`)

### Naming Conventions
- Backend: PascalCase classes, camelCase methods, UPPER_SNAKE_CASE constants
- Frontend: Same + `$` prefix for signals, file names kebab-case
- DTO files: `*.dto.ts`, Constants: `*.consts.ts`, Tests: `*.spec.ts`

### Dependency Injection
- Constructor injection always
- Services singleton by default (only `Scope.REQUEST` when needed)
- Depend on interfaces, not implementations

### Git & CI/CD
- **Branch naming**: `feature/name`, `bugfix/name`, `hotfix/name`
- **Commits**: Descriptive, consider conventional: `feat:`, `fix:`, `refactor:`
- **PR Checklist**:
  - [ ] Follow team conventions
  - [ ] No `npm audit` issues
  - [ ] No deprecated packages
  - [ ] Logging: INFO and ERROR levels
  - [ ] Swagger: All endpoints documented (backend)
  - [ ] Database migrations included (if needed)
  - [ ] Zero "any" types

### Database Migrations
- **Naming**: `YYYYMMDDHHMMSS_descriptive_name.ts`
- **Rollback**: Both `up()` and `down()` functions, fully reversible
- **Zero-downtime**: Nullable columns, non-locking indexes, batching

## Error Handling & HTTP Status Codes
- **4xx**: Client errors only (invalid input, auth failure, not found)
- **5xx**: Server errors only (unhandled exceptions)
- Error response: `{ statusCode, message, timestamp, endpoint, userId?, requestId }`
- Custom exception hierarchy: `BadRequestException`, `ConflictException`, `NotFoundException`

## Architectural Suggestion (Not Blocking)
- **Background Jobs**: When operations >5 seconds, consider async queue (Bull, RabbitMQ)
"""


class CodeReviewAgent:
    """Automated code review agent using Claude and Tavor conventions"""
    
    def __init__(self):
        self.validate_config()
        self.gitlab_api = f"{GITLAB_URL}/api/v4"
        self.mr_api = f"{self.gitlab_api}/projects/{PROJECT_ID}/merge_requests/{MR_IID}"
        self.mr_title = None
        self.mr_description = None
    
    def validate_config(self) -> None:
        """Validate all required environment variables"""
        missing = []
        
        print("🔍 DEBUG: Environment Variables")
        print(f"   CLAUDE_API_URL: {CLAUDE_API_URL}")
        print(f"   CLAUDE_API_KEY: {CLAUDE_API_KEY[:20] if CLAUDE_API_KEY else 'NOT SET'}...")
        print(f"   GITLAB_TOKEN: {GITLAB_TOKEN[:20] if GITLAB_TOKEN else 'NOT SET'}...")
        print(f"   PROJECT_ID: {PROJECT_ID}")
        print(f"   MR_IID: {MR_IID}")
        print()
        
        if not CLAUDE_API_KEY:
            missing.append("CLAUDE_API_KEY")
        if not GITLAB_TOKEN:
            missing.append("GITLAB_TOKEN")
        if not PROJECT_ID:
            missing.append("CI_PROJECT_ID")
        if not MR_IID:
            missing.append("CI_MERGE_REQUEST_IID")
        
        if missing:
            print(f"❌ Missing required environment variables: {', '.join(missing)}")
            sys.exit(1)
        
        print(f"✅ Configuration valid")
        print(f"   Claude API: {CLAUDE_API_URL}")
        print(f"   GitLab: {GITLAB_URL}")
        print(f"   Project: {PROJECT_ID}, MR: {MR_IID}")
    
    def get_mr_details(self) -> None:
        """Fetch MR title and description"""
        print("\n📋 Fetching MR details...")
        response = requests.get(
            self.mr_api,
            headers={"PRIVATE-TOKEN": GITLAB_TOKEN}
        )
        response.raise_for_status()
        
        data = response.json()
        self.mr_title = data.get("title", "")
        self.mr_description = data.get("description", "")
        
        print(f"   Title: {self.mr_title}")
    
    def get_mr_diff(self) -> str:
        """Fetch the code diff from the MR"""
        print("📥 Fetching code diff...")
        response = requests.get(
            f"{self.mr_api}/changes",
            headers={"PRIVATE-TOKEN": GITLAB_TOKEN}
        )
        response.raise_for_status()
        
        changes = response.json()
        diff_text = ""
        
        for change in changes.get("changes", []):
            new_path = change.get("new_path", change.get("old_path", "unknown"))
            diff_text += f"\n\n{'='*60}\nFILE: {new_path}\n{'='*60}\n"
            diff_text += change.get("diff", "[No diff content]")
        
        # Truncate if too large (Claude has token limits)
        max_size = 15000
        if len(diff_text) > max_size:
            diff_text = diff_text[:max_size] + f"\n\n[... diff truncated, total size: {len(diff_text)} chars ...]"
        
        print(f"   Got diff ({len(diff_text)} chars)")
        return diff_text
    
    def get_changed_files(self) -> List[str]:
        """Get list of changed files and their types"""
        response = requests.get(
            f"{self.mr_api}/changes",
            headers={"PRIVATE-TOKEN": GITLAB_TOKEN}
        )
        response.raise_for_status()
        
        changes = response.json()
        files = []
        for change in changes.get("changes", []):
            new_path = change.get("new_path", change.get("old_path", "unknown"))
            files.append(new_path)
        
        print(f"   Files changed: {len(files)}")
        return files
    
    def review_with_claude(self, diff: str, files: List[str]) -> Dict[str, Any]:
        """Call Claude API to review the code"""
        print("\n🤖 Calling Claude for review...")
        
        files_str = "\n".join([f"  - {f}" for f in files])
        
        prompt = f"""You are an expert code reviewer for the Tavor project. Review this merge request code against our team's Tavor Code Review Conventions.

## PROJECT: Tavor
MR Title: {self.mr_title}

## CHANGED FILES
{files_str}

## TAVOR SKILL (Our Code Review Conventions)
{TAVOR_SKILL}

## CODE DIFF
{diff}

---

IMPORTANT: Provide your review as JSON ONLY (no other text).

Analyze the code and identify:
1. **Critical Issues (BLOCKERS)**: SRP violations, zero "any" type violations, missing Swagger decorators (backend), deprecated packages, security issues
2. **Major Issues (WARNINGS)**: Logic complexity, missing logging, poor naming, type safety issues, missing error handling
3. **Minor Issues (SUGGESTIONS)**: Code simplicity improvements, documentation suggestions, architectural recommendations

Format your response as valid JSON:
{{
  "summary": "Brief overview of the change and overall assessment",
  "approval_decision": "APPROVE|REQUEST_CHANGES|COMMENT",
  "approval_reason": "Why you made this decision",
  "score": 8,
  "critical_issues": [
    {{
      "severity": "blocker",
      "file": "path/to/file.ts",
      "line": 45,
      "message": "Missing @ApiResponse decorator for 401 Unauthorized",
      "convention": "Every endpoint must have @ApiResponse for all status codes"
    }}
  ],
  "major_issues": [
    {{
      "severity": "warning",
      "file": "path/to/file.ts",
      "line": 120,
      "message": "Method has 35 lines, consider breaking into smaller functions",
      "convention": "Methods should be max 30 lines"
    }}
  ],
  "minor_issues": [
    {{
      "severity": "suggestion",
      "file": "path/to/file.ts",
      "line": 60,
      "message": "Consider using @IsOptional() for this property",
      "convention": "Mark optional DTO properties with @IsOptional()"
    }}
  ]
}}

Respond ONLY with the JSON, no other text."""
        
        try:
            response = requests.post(
                f"{CLAUDE_API_URL}/v1/messages",
                headers={
                    "Content-Type": "application/json",
                    "x-api-key": CLAUDE_API_KEY,
                    "anthropic-version": "2023-06-01"
                },
                json={
                    "model": "claude-opus-4.5",
                    "max_tokens": 2000,
                    "messages": [
                        {"role": "user", "content": prompt}
                    ]
                },
                timeout=60
            )
            response.raise_for_status()
            
            data = response.json()
            review_text = data["content"][0]["text"]
            
            # Extract JSON from response
            json_match = re.search(r'\{.*\}', review_text, re.DOTALL)
            if json_match:
                review = json.loads(json_match.group())
            else:
                raise ValueError(f"Could not find JSON in response: {review_text[:200]}")
            
            print(f"   ✅ Review complete (score: {review.get('score', '?')}/10, decision: {review.get('approval_decision', '?')})")
            return review
            
        except requests.exceptions.ConnectionError:
            print(f"   ❌ Could not connect to Claude API at {CLAUDE_API_URL}")
            print(f"   Make sure Claude is running and accessible")
            raise
        except requests.exceptions.Timeout:
            print(f"   ❌ Claude API request timed out")
            raise
        except json.JSONDecodeError as e:
            print(f"   ❌ Invalid JSON from Claude: {e}")
            raise
    
    def format_review_comment(self, review: Dict[str, Any]) -> str:
        """Format review results as GitLab MR comment"""
        
        decision = review.get("approval_decision", "COMMENT")
        score = review.get("score", "?")
        summary = review.get("summary", "No summary available")
        reason = review.get("approval_reason", "")
        
        # Decision emoji and status
        decision_emoji = {
            "APPROVE": "✅",
            "REQUEST_CHANGES": "⚠️",
            "COMMENT": "💬"
        }.get(decision, "❓")
        
        decision_text = {
            "APPROVE": "APPROVE - Ready to merge",
            "REQUEST_CHANGES": "REQUEST CHANGES - Address issues before merging",
            "COMMENT": "COMMENT - Review observations"
        }.get(decision, decision)
        
        comment = f"""## {decision_emoji} Automated Code Review by Tavor

**Score:** {score}/10  
**Decision:** {decision_emoji} {decision_text}

### Summary
{summary}

"""
        
        # Critical issues (blockers)
        critical = review.get("critical_issues", [])
        if critical:
            comment += "### 🛑 CRITICAL Issues (Blockers - Must Fix)\n\n"
            for i, issue in enumerate(critical[:10], 1):
                file = issue.get("file", "unknown")
                line = issue.get("line", "?")
                message = issue.get("message", "")
                convention = issue.get("convention", "")
                
                comment += f"{i}. **{file}:{line}**\n"
                comment += f"   {message}\n"
                if convention:
                    comment += f"   💡 _Convention: {convention}_\n"
                comment += "\n"
            
            if len(critical) > 10:
                comment += f"   ... and {len(critical) - 10} more critical issues\n\n"
        
        # Major issues (warnings)
        major = review.get("major_issues", [])
        if major:
            comment += "### ⚠️ MAJOR Issues (Warnings - Should Fix)\n\n"
            for i, issue in enumerate(major[:8], 1):
                file = issue.get("file", "unknown")
                line = issue.get("line", "?")
                message = issue.get("message", "")
                
                comment += f"{i}. **{file}:{line}** - {message}\n"
            
            if len(major) > 8:
                comment += f"   ... and {len(major) - 8} more major issues\n"
            comment += "\n"
        
        # Minor issues (suggestions)
        minor = review.get("minor_issues", [])
        if minor:
            comment += "### 💡 SUGGESTIONS (Nice to Have)\n\n"
            for i, issue in enumerate(minor[:5], 1):
                file = issue.get("file", "unknown")
                message = issue.get("message", "")
                comment += f"{i}. **{file}** - {message}\n"
            
            if len(minor) > 5:
                comment += f"\n   ... and {len(minor) - 5} more suggestions\n"
            comment += "\n"
        
        # Decision reason
        if reason:
            comment += f"### Decision Reason\n{reason}\n\n"
        
        comment += "---\n"
        comment += "_🤖 Review by Claude + Tavor Conventions_  \n"
        comment += "_[Tavor GitHub](https://github.com/liorpoleg/tavor-skill)_"
        
        return comment
    
    def post_review_comment(self, comment: str) -> None:
        """Post review as comment on the MR"""
        print("\n📤 Posting review to GitLab MR...")
        
        response = requests.post(
            f"{self.mr_api}/notes",
            headers={"PRIVATE-TOKEN": GITLAB_TOKEN},
            json={"body": comment}
        )
        response.raise_for_status()
        print("   ✅ Review posted successfully!")
    
    def save_review_result(self, review: Dict[str, Any]) -> None:
        """Save review result to file for CI/CD pipeline"""
        with open("review_result.json", "w") as f:
            json.dump(review, f, indent=2)
        print("   ✅ Review result saved to review_result.json")
    
    def run(self) -> None:
        """Main workflow"""
        print("=" * 60)
        print("🚀 Tavor Automated Code Review Agent")
        print("=" * 60)
        
        try:
            # Step 1: Get MR details
            self.get_mr_details()
            
            # Step 2: Get code diff
            diff = self.get_mr_diff()
            files = self.get_changed_files()
            
            # Step 3: Review with Claude
            review = self.review_with_claude(diff, files)
            
            # Step 4: Format comment
            comment = self.format_review_comment(review)
            
            # Step 5: Post to GitLab
            self.post_review_comment(comment)
            
            # Step 6: Save result for CI/CD
            self.save_review_result(review)
            
            print("\n" + "=" * 60)
            print("✨ Code review completed successfully!")
            print("=" * 60)
            
        except Exception as e:
            print(f"\n❌ Error during review: {e}")
            import traceback
            traceback.print_exc()
            
            # Post error comment
            error_comment = f"""## ❌ Automated Review Failed

There was an error during the automated code review:

```
{type(e).__name__}: {str(e)}
```

**Troubleshooting:**
1. Check that Claude API is running and accessible at: `{CLAUDE_API_URL}`
2. Verify GitLab token has `api` scope
3. Check CI/CD pipeline logs for detailed error messages

---
_🤖 Review by Tavor_"""
            
            try:
                self.post_review_comment(error_comment)
            except Exception as post_error:
                print(f"Could not post error comment: {post_error}")
            
            sys.exit(1)


if __name__ == "__main__":
    agent = CodeReviewAgent()
    agent.run()
