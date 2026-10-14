# App / System Spec — input template for PROJECT KICKOFF breakdown

> Use this when starting development of a NEW system or app.
> Output of breakdown: Epics → Features/Stories → Tasks (initial backlog, phased).
> Save as `docs/specs/<system-name>.md`.

## 1. System overview
What is this app/system, who uses it, what problem does it solve? (1 paragraph)

## 2. User roles & personas
| Role | Description | Main goals |
|---|---|---|

## 3. Functional description (the core input)
List every function/module. For each:

### 3.x <Module / Screen name>
- **Description**: what the user can do here
- **Main flows**: step-by-step happy path
- **Edge cases / business rules**: validation, permissions, limits
- **Inputs / outputs / data involved**:
- **Priority**: Must / Should / Could (MoSCoW)

## 4. Screens / UI inventory (if app has UI)
| Screen | Role access | Key components | Wireframe link |
|---|---|---|---|

## 5. Data model (draft)
Main entities and relationships. ERD link if available.

## 6. Integrations & external systems
| System | Direction | Protocol/API | Auth |
|---|---|---|---|

## 7. Non-functional requirements
Performance targets, security/compliance, availability, i18n (e.g. JP/VN), data volume.

## 8. Tech stack & architecture decisions
Languages, frameworks, cloud services (e.g. Azure Functions, ADF, Fabric), CI/CD, environments.

## 9. Phases / milestones
| Phase | Scope (which modules) | Start date | Target date |
|---|---|---|---|

## 10. Out of scope (v1)
Explicitly list what will NOT be built now.

## 11. Open questions
Each blocking unknown becomes a spike task.
