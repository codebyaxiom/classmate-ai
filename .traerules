# 🤖 Project Rules & AI-Native Development Protocol (Anchor)
> **Usage:** Place this file in the root directory of your project (named `CLAUDE.md`, `GEMINI.md`, or `.cursorrules`).
> It forces all AI agents (Claude Code, Antigravity, Cursor, etc.) to strictly obey your Obsidian blueprints on every turn.

---

## 🎯 Role Hierarchy & User Alignment
- **Jerald (User):** System Architect & Decision Maker.
- **AI Agent:** Senior Implementer & Pair Programmer.
- **Developer Profile:** Read `D:\Axiom_Vault\02 Areas\Developer Profile.md` for Jerald's preferences (Strict Dark Mode, Drive D: partition mandate, zero em dashes, humanized technical English, 5-Phase Playbook).
- **Protocol:** The agent must never unilaterally change architecture, invent endpoints, or implement multiple features in one unreviewed blast.

---

## 📜 Master Living Specification
- **Master Spec Path:** `D:\Axiom_Vault\01 Projects\CLASSMATE-AI.md`
- **Rule:** Before proposing or writing code, read the Master Spec to understand the current phase, database entities, and constraints.
- **Rule (Rule 10):** When a feature or milestone phase is completed, update the action checklist and YAML frontmatter in the Master Spec.

---

## 🛑 Strict Engineering Constraints (5-Phase Playbook)

### 1. No "Vibe Coding"
- Never generate an entire application, multi-table database, and multiple frontend views in a single prompt.
- Work **one feature / one component per turn**.

### 2. Specification First
- If adding or altering features, confirm the database schema, route structure, and user flow in the Master Spec first.
- If an ambiguous decision arises, ask or state the minimal assumption—do not hallucinate.

### 3. Modular Implementation
- Keep components focused and decoupled.
- Follow existing patterns in the codebase (e.g., Zustand for state, Tailwind for styling, Express for API).

### 4. Empirical Verification (No Guesswork)
- Never declare a task complete without running verification (e.g., `npm run build`, `npm test`, or verifying endpoints).
- If a build or runtime error occurs, inspect the real terminal traceback rather than guessing.

### 5. Clean Code Standards
- Maintain strict separation of concerns.
- Do not add random dependencies without confirmation.
- Write clean, self-documenting code with defensive error handling.

### 6. Zero-Downtime Debugging Protocol (Rule 2)
- **Cloud Apps (Vercel):** Never debug on `main`. Create a git branch (e.g. `debug/xyz`) and test on the Vercel Preview URL so live users experience zero interruption.
- **Phone NAS (Termux):** Never edit live files on the phone via SSH (avoids PM2 restart loops and Android OOM kills). Debug and test on laptop (`D:\Projects`), then deploy clean files and run `pm2 reload <service>`.
- **Local Daemons (Axiom):** Run test instances on port offset `+100` (e.g. `8100`) pointing to a test database so the live watchdog-monitored daemon remains unaffected.

### 7. Universal AI Gateway Standard (OmniRoute — Rule 3)
- If this project requires LLM completions, vision OCR, or embeddings, standardize strictly on the universal OpenAI-compatible SDK pointing to `base_url="http://localhost:20128/v1"` and `api_key="omniroute"` (using `process.env.AI_GATEWAY_URL` / `os.getenv("AI_GATEWAY_URL")`).
- Do not introduce redundant vendor SDKs (`@google/genai`, `groq-sdk`, `@anthropic-ai/sdk`) or duplicate upstream API keys across project folders.
- Request intent aliases (`model="auto"`, `"fast"`, `"smart"`, `"vision"`). OmniRoute dynamically resolves free-tier providers and transparently handles 429 rate-limit failover.

---

## 🔄 Session Protocol (Institutional Memory & Rule 10)

### On Session Start
1. Read `D:\Axiom_Vault\02 Areas\Developer Profile.md` to ground yourself in Jerald's developer profile and standards.
2. Read `D:\Axiom_Vault\VAULT_RULES.md` for the latest operating rules.
3. Read `D:\Axiom_Vault\03 Resources\Lessons Learned\_Lessons Index.md` and review any lessons relevant to this project's tech stack.
4. Read the Master Spec at `D:\Axiom_Vault\01 Projects\CLASSMATE-AI.md` to understand the current phase and progress.
5. Apply documented patterns and actively avoid documented pitfalls from past sessions.

### On Session End (Mandatory Progress Sync — Rule 10)
1. **Capture lessons (Rule 7):** For each significant pattern, bug fix, architectural decision, or gotcha encountered during this session, create a new file in `D:\Axiom_Vault\03 Resources\Lessons Learned\` following the `Lesson Learned Template`.
   - Filename: `YYYY-MM-DD -- <Short Descriptive Title>.md`
   - Fill in: category, project (`CLASSMATE-AI`), agent (your name), severity, date
   - Include: Context, Problem/Discovery, Solution/Pattern, Key Takeaway
2. **Synchronize Master Spec (Rule 10):**
   - Update YAML frontmatter: `updated:` (today's date), `status:` (accurate state), `tech_stack:` (new additions)
   - Update Session Checkpoint: Current Phase, Last Completed, Blockers
   - Update Action Checklist: check off completed tasks and append newly scoped tasks
3. **Notify the user:** Summarize progress, verify tests, and state what was synchronized to Obsidian.

