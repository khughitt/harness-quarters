/command _code_audit

## Code Audit for AI-Generated Code Patterns

Please conduct a comprehensive audit of the codebase to identify potential issues commonly associated with LLM-generated code, as well as general code health indicators.

### Areas to Examine

#### 1. Incomplete or Placeholder Implementations
- TODO/FIXME comments without resolution
- Stub methods returning hardcoded values or throwing NotImplementedException
- Mock implementations outside of test directories
- Functions with only pass/return statements or minimal logic
- Unimplemented error handling (empty catch blocks, generic error messages)

#### 2. Code Duplication and Redundancy
- Near-duplicate functions with minor variations
- Replicated business logic across modules
- Copy-pasted code blocks with slight modifications
- Redundant utility functions that duplicate standard library features

#### 3. AI-Generated Naming Patterns
- Overly generic prefixes: "Unified", "Consolidated", "Enhanced", "Advanced", "Improved"
- Redundant suffixes: "Manager", "Handler", "Processor", "Controller" used excessively
- Inconsistent naming conventions within the same module
- Overly verbose or unnecessarily descriptive names

#### 4. Architectural Issues
- Circular dependencies between modules
- Inconsistent abstraction levels (mixing high and low-level operations)
- Over-engineering simple functionality
- Missing or incomplete dependency injection
- Hardcoded configuration values that should be externalized

#### 5. Documentation and Comments
- Generic, non-specific comments that don't add value
- Outdated comments that don't match implementation
- Missing critical documentation for complex logic
- Excessive commenting of obvious operations

#### 6. Testing Gaps
- Test files with placeholder assertions
- Tests that don't actually test the functionality
- Missing edge case coverage
- Hardcoded test data without clear purpose

#### 7. Type Safety and Validation Issues
- Excessive use of 'any' types (TypeScript) or dynamic types
- Missing input validation
- Incomplete type definitions or interfaces
- Inconsistent null/undefined handling

### Priority Scoring Guidelines

Assign a priority score (1-10) to each issue based on:
- **Impact on Production** (weight: 40%): Could this cause runtime errors, data loss, or system failures?
- **Security Risk** (weight: 30%): Does this create vulnerabilities or expose sensitive data?
- **Maintainability** (weight: 20%): How much does this hinder future development?
- **Technical Debt** (weight: 10%): How much effort to fix vs. compound interest if left?

Priority Scale:
- 9-10: Critical - Production blocker or security vulnerability
- 7-8: High - Significant risk or major maintainability issue
- 5-6: Medium - Should be addressed in next sprint
- 3-4: Low - Can be scheduled for future refactoring
- 1-2: Minor - Nice to fix but not urgent

### Output Format

Generate a structured report, saved to `doc/reports/code-audit-<date>.md` with the following sections:

```markdown
# Code Audit Report

## Executive Summary
- Total issues found: [count]
- Critical issues (priority 9-10): [count]
- High priority issues (priority 7-8): [count]
- Risk assessment: [Low/Medium/High]

## Findings by Component

### Backend
#### [Subsystem/Module Name]

**Issues (sorted by priority):**

1. **[Priority: X.X]** [Issue Title]
   - **Type**: [e.g., Incomplete Implementation]
   - **Severity**: [Critical/High/Medium/Low]
   - **Location**: `[file:line]`
   - **Description**: [specific issue]
   - **Impact**: [what could go wrong]
   - **Recommendation**: [suggested fix]
   - **Estimated effort**: [hours/days]

2. **[Priority: X.X]** [Next Issue]
   [Same structure, sorted by decreasing priority]

### Frontend
#### [Subsystem/Module Name]

**Issues (sorted by priority):**

[Same structure as backend, sorted by decreasing priority]

## Metrics Summary
- Code duplication percentage
- Test coverage gaps
- Number of TODO/FIXME comments
- Files with suspicious AI-pattern names
- Average priority score across all issues

## Top 10 Priority Actions (All Components)
1. **[Priority: X.X]** [Component/Module] - [Issue]
2. **[Priority: X.X]** [Component/Module] - [Issue]
3. [Continue for top 10 across entire codebase]

## Remediation Roadmap
### Immediate (Priority 9-10)
- [List of critical issues to fix immediately]

### This Sprint (Priority 7-8)
- [High priority issues]

### Next Sprint (Priority 5-6)
- [Medium priority issues]

### Backlog (Priority 1-4)
- [Lower priority improvements]
