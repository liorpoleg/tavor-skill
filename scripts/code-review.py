#!/usr/bin/env python3
"""
Tavor Automated Code Review Agent
Runs on every GitLab merge request to review code against team conventions

Usage:
  LLM_ENDPOINT=http://localhost:8000 \
  LLM_MODEL=claude-opus-4-1-20250805 \
  LLM_API_KEY=your_key \
  GITLAB_TOKEN=your_token \
  CI_PROJECT_ID=123 \
  CI_MERGE_REQUEST_IID=456 \
  CI_SERVER_URL=https://gitlab.example.com \
  python scripts/code-review.py

Environment Variables:
  LLM_ENDPOINT     - LLM API endpoint (e.g., http://localhost:8000 or https://api.anthropic.com)
  LLM_MODEL        - Model name (e.g., claude-opus-4-1-20250805)
  LLM_API_KEY      - API key for authentication
  GITLAB_TOKEN     - GitLab personal access token
  CI_PROJECT_ID    - GitLab project ID (set by CI/CD)
  CI_MERGE_REQUEST_IID - MR ID (set by CI/CD)
  CI_SERVER_URL    - GitLab server URL
"""

import os
import sys
import requests
import json
import re
from typing import Optional, List, Dict, Any, Tuple


# Configuration from environment
LLM_ENDPOINT = os.getenv("LLM_ENDPOINT", "http://localhost:8000")
LLM_MODEL = os.getenv("LLM_MODEL", "claude-opus-4-1-20250805")
LLM_API_KEY = os.getenv("LLM_API_KEY")
GITLAB_URL = os.getenv("CI_SERVER_URL", "https://gitlab.example.com")
GITLAB_TOKEN = os.getenv("GITLAB_TOKEN")
PROJECT_ID = os.getenv("CI_PROJECT_ID")
MR_IID = os.getenv("CI_MERGE_REQUEST_IID")


class LLMError(Exception):
    """Raised when LLM request fails"""
    pass


class LLMClient:
    """Client for communicating with LLM API - supports multiple providers"""
    
    def __init__(self):
        # Endpoint is the only outbound URL in this system
        self.endpoint = LLM_ENDPOINT.strip().rstrip('/')
        self.model = LLM_MODEL
        self._session = requests.Session()
        
        if not self.endpoint:
            raise LLMError('LLM_ENDPOINT is not configured.')
        if not self.model:
            raise LLMError('LLM_MODEL is not configured.')
        
        # Detect API format based on endpoint
        self.api_format = self._detect_api_format()
        
        api_key = LLM_API_KEY
        if api_key:
            # Both authentication methods for compatibility
            self._session.headers['Authorization'] = f'Bearer {api_key}'
            self._session.headers['x-api-key'] = api_key
        
        self._session.headers['Content-Type'] = 'application/json'
        # Anthropic-specific header (other providers ignore it)
        self._session.headers['anthropic-version'] = '2023-06-01'
    
    def _detect_api_format(self) -> str:
        """Detect which API format this endpoint uses"""
        endpoint_lower = self.endpoint.lower()
        
        # Check for known endpoints
        if 'anthropic.com' in endpoint_lower or '/v1/messages' in endpoint_lower:
            return 'anthropic'
        elif 'generativelanguage.googleapis.com' in endpoint_lower:
            return 'gemini'
        elif 'openai.com' in endpoint_lower:
            return 'openai'
        elif 'chat/completions' in endpoint_lower:
            return 'openai'  # OpenAI-compatible format
        else:
            # Default to OpenAI-compatible (most common)
            return 'openai'
    
    def _post(self, messages: List[Dict[str, str]], max_tokens: int = 2000, 
              temperature: float = 0.3) -> str:
        """Send a message to the LLM and return the response"""
        
        try:
            if self.api_format == 'anthropic':
                response = self._post_anthropic(messages, max_tokens, temperature)
            else:  # OpenAI-compatible format (Gemini, OpenAI, etc.)
                response = self._post_openai_compatible(messages, max_tokens, temperature)
            
            response.raise_for_status()
        except requests.exceptions.ConnectionError as e:
            raise LLMError(f'Could not connect to LLM at {self.endpoint}: {e}') from e
        except requests.exceptions.Timeout as e:
            raise LLMError(f'LLM request timed out: {e}') from e
        except requests.exceptions.RequestException as e:
            raise LLMError(f'LLM request failed: {e}') from e
        
        return self._extract_response(response)
    
    def _post_anthropic(self, messages: List[Dict[str, str]], max_tokens: int, 
                        temperature: float) -> requests.Response:
        """POST to Anthropic API format"""
        url = f"{self.endpoint}/v1/messages" if not self.endpoint.endswith('/messages') else self.endpoint
        
        payload = {
            'model': self.model,
            'messages': messages,
            'max_tokens': max_tokens,
            'temperature': temperature
        }
        
        return self._session.post(url, json=payload, timeout=60)
    
    def _post_openai_compatible(self, messages: List[Dict[str, str]], max_tokens: int,
                                temperature: float) -> requests.Response:
        """POST to OpenAI-compatible API format (Gemini, OpenAI, etc.)"""
        # Endpoint already includes the full path, don't append anything
        url = self.endpoint
        
        payload = {
            'model': self.model,
            'messages': messages,
            'max_tokens': max_tokens,
            'temperature': temperature
        }
        
        return self._session.post(url, json=payload, timeout=60)
    
    def _extract_response(self, response: requests.Response) -> str:
        """Extract text from response - handles multiple formats"""
        try:
            data = response.json()
            
            # Try Anthropic format first
            try:
                return data['content'][0]['text']
            except (KeyError, IndexError, TypeError):
                pass
            
            # Try OpenAI format (Gemini, OpenAI, etc.)
            try:
                return data['choices'][0]['message']['content']
            except (KeyError, IndexError, TypeError):
                pass
            
            # Try alternate Anthropic format
            try:
                return data['content'][0]['message']['content']
            except (KeyError, IndexError, TypeError):
                pass
            
            # If nothing worked, raise error with the actual response for debugging
            raise LLMError(f'Unexpected LLM response format. Got: {str(data)[:500]}')
            
        except (ValueError, json.JSONDecodeError) as e:
            raise LLMError(f'Invalid JSON response from LLM: {e}') from e
    
    def complete(self, prompt: str, max_tokens: int = 2000) -> str:
        """Single message completion"""
        return self._post([{'role': 'user', 'content': prompt}], 
                         max_tokens=max_tokens)
    
    def chat(self, system_prompt: str, messages: List[Dict[str, str]], 
             max_tokens: int = 2000) -> str:
        """Multi-turn chat with system prompt"""
        all_messages = [{'role': 'system', 'content': system_prompt}] + messages
        return self._post(all_messages, max_tokens=max_tokens)


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
        print(f"   LLM_ENDPOINT: {LLM_ENDPOINT}")
        print(f"   LLM_MODEL: {LLM_MODEL}")
        print(f"   LLM_API_KEY: {LLM_API_KEY[:20] if LLM_API_KEY else 'NOT SET'}...")
        print(f"   GITLAB_TOKEN: {GITLAB_TOKEN[:20] if GITLAB_TOKEN else 'NOT SET'}...")
        print(f"   PROJECT_ID: {PROJECT_ID}")
        print(f"   MR_IID: {MR_IID}")
        print()
        
        if not LLM_ENDPOINT:
            missing.append("LLM_ENDPOINT")
        if not LLM_MODEL:
            missing.append("LLM_MODEL")
        if not LLM_API_KEY:
            missing.append("LLM_API_KEY")
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
        print(f"   LLM API: {LLM_ENDPOINT} (model: {LLM_MODEL})")
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
    
    def get_mr_diff(self) -> Tuple[str, int]:
        """Fetch the code diff from the MR - returns full diff and total size"""
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
        
        total_size = len(diff_text)
        print(f"   Got diff ({total_size} chars)")
        return diff_text, total_size
    
    def chunk_diff(self, diff: str, chunk_size: int = 18000) -> List[Tuple[str, int, int]]:
        """
        Split diff into chunks while preserving file boundaries
        Returns list of (chunk_text, chunk_num, total_chunks)
        """
        chunks = []
        lines = diff.split('\n')
        current_chunk = []
        current_size = 0
        
        for line in lines:
            line_size = len(line) + 1  # +1 for newline
            
            # If adding this line would exceed chunk_size, save current chunk
            if current_size + line_size > chunk_size and current_chunk:
                chunks.append('\n'.join(current_chunk))
                current_chunk = []
                current_size = 0
            
            current_chunk.append(line)
            current_size += line_size
        
        # Add remaining chunk
        if current_chunk:
            chunks.append('\n'.join(current_chunk))
        
        # Return with chunk number and total
        return [(chunk, i+1, len(chunks)) for i, chunk in enumerate(chunks)]
    
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
    
    def review_chunk(self, diff_chunk: str, chunk_num: int, total_chunks: int, 
                     files: List[str], llm: LLMClient) -> Dict[str, Any]:
        """Review a single chunk of the diff"""
        
        chunk_indicator = f" (Chunk {chunk_num}/{total_chunks})" if total_chunks > 1 else ""
        
        files_str = "\n".join([f"  - {f}" for f in files])
        
        prompt = f"""You are an expert code reviewer for the Tavor project. Review this merge request code against our team's Tavor Code Review Conventions.

NOTE: You are reviewing chunk {chunk_num} of {total_chunks}. Focus on issues in this chunk.

## PROJECT: Tavor
MR Title: {self.mr_title}

## CHANGED FILES (in this chunk)
{files_str}

## TAVOR SKILL (Our Code Review Conventions)
{TAVOR_SKILL}

## CODE DIFF - CHUNK {chunk_num} of {total_chunks}
{diff_chunk}

---

IMPORTANT: Provide your review as JSON ONLY (no other text).

Analyze the code and identify:
1. **Critical Issues (BLOCKERS)**: SRP violations, zero "any" type violations, missing Swagger decorators (backend), deprecated packages, security issues
2. **Major Issues (WARNINGS)**: Logic complexity, missing logging, poor naming, type safety issues, missing error handling
3. **Minor Issues (SUGGESTIONS)**: Code simplicity improvements, documentation suggestions, architectural recommendations

Format your response as valid JSON:
{{
  "summary": "Review of chunk {chunk_num}",
  "approval_decision": "APPROVE|REQUEST_CHANGES|COMMENT",
  "approval_reason": "Why you made this decision for this chunk",
  "score": 8,
  "critical_issues": [...],
  "major_issues": [...],
  "minor_issues": [...]
}}

Respond ONLY with the JSON, no other text."""
        
        try:
            review_text = llm.complete(prompt, max_tokens=4000)
            
            # Extract JSON from response
            json_match = re.search(r'\{.*\}', review_text, re.DOTALL)
            if json_match:
                review = json.loads(json_match.group())
            else:
                raise ValueError(f"Could not find JSON in response: {review_text[:200]}")
            
            print(f"   ✅ Chunk {chunk_num}/{total_chunks} reviewed")
            return review
            
        except LLMError as e:
            print(f"   ❌ LLM Error on chunk {chunk_num}: {e}")
            raise
        except json.JSONDecodeError as e:
            print(f"   ❌ Invalid JSON from LLM on chunk {chunk_num}: {e}")
            raise
    
    def merge_chunk_reviews(self, reviews: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Merge reviews from multiple chunks into a single review"""
        
        if not reviews:
            return {
                "summary": "No reviews to merge",
                "approval_decision": "COMMENT",
                "approval_reason": "No code was reviewed",
                "score": 0,
                "critical_issues": [],
                "major_issues": [],
                "minor_issues": []
            }
        
        if len(reviews) == 1:
            return reviews[0]
        
        # Merge multiple reviews
        merged = {
            "summary": f"Full MR review across {len(reviews)} chunks. " + 
                      " ".join([r.get("summary", "") for r in reviews if r.get("summary")]),
            "approval_decision": "REQUEST_CHANGES" if any(
                r.get("approval_decision") == "REQUEST_CHANGES" for r in reviews
            ) else ("APPROVE" if all(
                r.get("approval_decision") in ["APPROVE", "COMMENT"] for r in reviews
            ) else "COMMENT"),
            "approval_reason": "Review based on full diff analysis across all chunks. " +
                             " ".join([r.get("approval_reason", "") for r in reviews if r.get("approval_reason")]),
            "score": int(sum(r.get("score", 0) for r in reviews) / len(reviews)),
            "critical_issues": [],
            "major_issues": [],
            "minor_issues": []
        }
        
        # Merge and deduplicate issues
        seen_issues = set()
        for review in reviews:
            for issue_type in ["critical_issues", "major_issues", "minor_issues"]:
                for issue in review.get(issue_type, []):
                    issue_key = (
                        issue.get("file", ""),
                        issue.get("line", ""),
                        issue.get("message", "")
                    )
                    if issue_key not in seen_issues:
                        seen_issues.add(issue_key)
                        merged[issue_type].append(issue)
        
        return merged
    
    def review_with_claude(self, diff: str, total_size: int, files: List[str], llm: LLMClient) -> Dict[str, Any]:
        """Call LLM to review the code - handles large diffs by chunking"""
        print("\n🤖 Calling LLM for review...")
        
        # Decide if we need to chunk
        chunk_size = 18000
        
        if total_size <= chunk_size:
            # Small diff - review as-is
            print(f"   Single review ({total_size} chars)")
            return self.review_chunk(diff, 1, 1, files, llm)
        
        # Large diff - chunk it
        print(f"   Large diff ({total_size} chars) - chunking for full review")
        chunked = self.chunk_diff(diff, chunk_size)
        print(f"   Split into {len(chunked)} chunks")
        
        reviews = []
        for chunk_text, chunk_num, total_chunks in chunked:
            print(f"   Processing chunk {chunk_num}/{total_chunks}...")
            review = self.review_chunk(chunk_text, chunk_num, total_chunks, files, llm)
            reviews.append(review)
        
        # Merge all reviews
        merged_review = self.merge_chunk_reviews(reviews)
        print(f"   ✅ Full review complete ({len(reviews)} chunks merged)")
        
        return merged_review
    
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
            # Initialize LLM client
            try:
                llm = LLMClient()
                print("✅ LLM Client initialized")
            except LLMError as e:
                print(f"❌ Failed to initialize LLM client: {e}")
                raise
            
            # Step 1: Get MR details
            self.get_mr_details()
            
            # Step 2: Get code diff
            diff, total_size = self.get_mr_diff()
            files = self.get_changed_files()
            
            # Step 3: Review with LLM (handles chunking automatically)
            review = self.review_with_claude(diff, total_size, files, llm)
            
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
1. Check that LLM is running and accessible at: `{LLM_ENDPOINT}` (model: {LLM_MODEL})
2. Verify LLM_API_KEY and LLM_MODEL are correctly configured
3. Verify GitLab token has `api` scope
4. Check CI/CD pipeline logs for detailed error messages

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
