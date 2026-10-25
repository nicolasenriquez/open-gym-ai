# OpenGym web verification cases

Reusable scenarios, not an execution report. Base: Spanish UI, kg/cm, isolated ephemeral
browser at `http://localhost:8080`. Start empty unless a case requires prior synthetic data.
Never use the user's profile. Follow the [skill](../SKILL.md) for health, driving and cleanup.

Record build/revision, environment, case IDs, pass/fail/pending and evidence in each run.
Historical failures are not expected behavior; revalidate them against the served build.
The guest runner covers one connected journey; inspect
[`guest-smoke.js`](../helpers/guest-smoke.js) for its actual assertions.
For L08/W04/X02 use the [UI regression guide](../../../../docs/dev/ui-accessibility-fixes.md).
A rendered route or a screenshot alone does not prove actions or persistence.

| ID | Preconditions and UI actions | Expected result / evidence |
| --- | --- | --- |
| G01 | Fresh profile; open root | Login without prior account; API health ok |
| G02 | Continue without account | Welcome, no bodyweight entries, local-data notice |
| G03 | Reload guest with synthetic data | No return to login or loss of records |
| G04 | Cancel passkey authentication | Recoverable message; no session or guest-data loss; needs authorized credentials setup |
| G05 | Sign in with local data | Explicit adoption decision; no silent overwrite; needs test account |
| G06 | Logout and sign in as second user | Previous user's data/media inaccessible; needs two test accounts |
| L01 | Search impossible exercise name | Zero results; no squat row |
| L02 | Search squat; open detail; Escape | Correct detail; return to catalogue |
| L03 | Combine muscle/type/equipment filters; clear | Intersection respected; reset restores catalogue |
| L04 | Exercises > By muscle > muscle | Coherent list; detail reachable; return preserves context |
| L05 | Switch cards/list; Show more | Same results; pagination without duplicates |
| L06 | Create personal exercise without media | Present in catalogue and usable in routine after reload |
| L07 | Load still and play exercise clip | Real media loads; controls and pause work |
| L08 | Open detail; Tab/Shift+Tab and screen reader | Named dialog; focus stays inside page modal; returns on close |
| P01 | Plan > Routines > New; name; add squat | Routine with 3 × 10 |
| P02 | Reload routine editor | Name and exercise preserved |
| P03 | Schedule > Monday > routine > Done; reload | Monday contains routine |
| P04 | Home > Load starter plan; select and confirm | Expected routines/schedule; prior history preserved |
| P05 | Home > Create my own plan | Plan reached; editing/creation accessible |
| P06 | Catalogue Plan and detail Add to my plan | Selected routine receives exercise once; check both entry points |
| P07 | Duplicate routine; edit copy | Original independent; distinct IDs; both survive reload |
| P08 | Reorder exercises; group superset; ungroup | Order/group persist and appear during workout |
| P09 | Two routines on one day; remove one | Combined start works; removal does not delete routine |
| P10 | Rotation; add routines/rest; finish session | Queue advances by contract; no reload skips |
| P11 | Change rotation to fixed week; cancel/confirm | Cancel preserves queue; confirm changes mode without deleting routines |
| P12 | Delete routine used in plan/history | Confirmation; consistent schedule; readable history; disposable profile only |
| P13 | Configure progression/deload/exercise rules | Valid persistent values; later prescriptions agree with pure-helper tests |
| W01 | Home > Choose another workout > routine | Three sets; active session |
| W02 | Minimize > Continue > reload; complete three sets; finish | Same workout; summary; exactly one completion |
| W03 | Start tab on rest and scheduled days | Correct chooser or scheduled routine |
| W04 | Select routine using Tab/Enter/Space | Reachable native control; keyboard starts routine |
| W05 | Freestyle; add exercise; finish | No routine required; correct history record |
| W06 | Edit weight/reps; mark/unmark set; reload | State and values preserved |
| W07 | Add/copy/remove set and exercise | Counts/navigation updated; no unrelated exercise changed |
| W08 | Finish partial session; cancel then confirm | Cancel retains session; confirm records only performed work |
| W09 | Discard workout | No history record; active removed only from disposable profile |
| W10 | Start/pause/adjust/skip rest | Coherent time; one alert; accessible controls |
| W11 | Log RIR/RPE and set/session notes | Present in reopened history and export |
| W12 | Switch Cards/List/Compact/Focus | Same data/current set; no session reset |
| W13 | Superset and timed/cardio exercise | Correct sequence, units and modality validation |
| H01 | Stats > All; reload history | One workout with three completed sets |
| H02 | Open saved workout from History | Correct routine and sets; compare export |
| H03 | Open via recent/calendar/Home done | Same record; return preserves context; check all entries |
| H04 | Edit saved session; leave; cancel/save | Coherent draft/confirmation; no duplicate record |
| H05 | Log past workout | Correct date/order; no live timer |
| H06 | Delete record; cancel then confirm | Cancel unchanged; confirm updates metrics; disposable data only |
| A01 | Stats after first session | One workout; actual sets; no invented bodyweight |
| A02 | Switch week/30d/90d/all; fatigue/strength | Period applied; explicit empty states; no invented data |
| A03 | Stats > Structural balance | Explicit empty/insufficient-data state |
| A04 | Several sessions; progression/e1RM | Charts agree with records, units and selected formula |
| B01 | Home bodyweight 72.5; save/reload | 72.5 kg visible; export value 72.5 |
| B02 | Measurements > Record; save empty | At-least-one-measurement validation; form remains open |
| B03 | Waist 85; save/reload | 85 cm; other fields empty |
| B04 | Stats Record/Goal/All weigh-ins | Equivalent entries; goal and edits persist |
| B05 | Negative/text/future/duplicate date/bodyfat >100 | Clear validation or explicit date policy; no record corruption |
| B06 | Custom measurement and selection | Updated form/chart; duplicate names rejected |
| B07 | Convert kg/lb, cm/in; label-only alternative | Explicit conversion; no double conversion on reload |
| F01 | Stats > Photos with no images | Useful empty state |
| F02 | Synthetic photo via finished session and gallery | Same session link; media persistence; synthetic fixture required |
| F03 | Two synthetic photos; compare/video/delete | Correct order; accessible comparison; clear limits/errors |
| C01 | Home > At the gym | Empty cards and add action |
| C02 | Import synthetic QR; edit label; reorder | Decodable code; label/order persist |
| C03 | Denied camera or image without QR | Clear recovery; no corrupt card; explicit permission setup |
| S01 | Settings search Theme | Accessible Theme result |
| S02 | Appearance/Home > Light; reload | Light theme persists |
| S03 | Change locale, exercise names/instructions; return | Complete translation; state preserved; correct locale |
| S04 | Equipment/plates/dumbbells/fine settings | Values persist and affect relevant screens |
| D01 | Data/backups > Export JSON | Real download includes routine, three done sets, weight and measurement |
| D02 | Import backup into second clean guest | Same data/media according to format |
| D03 | Corrupt JSON/ZIP and external CSV | Recoverable error; valid state not replaced |
| D04 | Import with data conflicts; cancel/choose resolution | Safe cancel; merge/replace only by explicit decision |
| D05 | Reset all; cancel then confirm | Cancel preserves; confirm clears only disposable profile |
| X01 | Visit admin, coach/setup, reminders as guest | Safe redirect/unavailable state; no privileged access |
| X02 | Cold guest access to coach/intake | Redirect or explicit unavailable state; no blank shell |
| X03 | Enabled Coach; consent; provider error | No call before consent; recoverable errors; test provider required |
| X04 | Accounts/devices/API/offline sync | Ownership/access/recovery contracts; separate authorized test stack |
| X05 | Installed PWA; offline; SW update | Starts offline; retains data; recoverable update |
| X06 | Android/iOS alarms/permissions/share/backup | Real-device verification with explicit permissions |

Prioritize import/restore, session cancel/edit/backfill, rotation/supersets/progression,
then media/permissions/offline/auth with disposable fixtures. Every relevant entry point
must be exercised. Keep account, assistive-technology and native scenarios pending until
those environments are actually tested; viewport emulation does not cover them.
