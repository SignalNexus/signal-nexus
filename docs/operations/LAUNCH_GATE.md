# Launch Gate

English is canonical. The Japanese mirror is [LAUNCH_GATE_JA.md](LAUNCH_GATE_JA.md).

This chapter freezes the repository state from which infrastructure execution may start. It does not create a host, a database, or a Render service. It does not run `workflow_dispatch`. The authority for the pin, the seven files, and success is [Community Deployment Guide](../COMMUNITY_DEPLOYMENT_GUIDE.md). This chapter does not add a required fact.

## 1. Frozen repository state

Record these from the caller repository before execution starts. A later commit is a new gate.

| Name | Required state |
| --- | --- |
| Branch | `main` |
| `core-pin` | The public SHA this environment will run |
| `uses` | The same SHA |
| `core_sha` | The same SHA |
| `venueadd/venues.yaml` | `venues: []` |
| Seven live runtime files | Committed. Accepted by `confirm` |
| Actions secrets | Empty until [Infrastructure Execution](INFRASTRUCTURE_EXECUTION.md) |
| Actions variables | Empty until that chapter |
| `VENUEADD_READ_TOKEN` | Unset |

## 2. Frozen runtime hashes

Record `sha256sum` of the seven live files at the frozen commit. The first successful deploy matches those hashes in the deploy log and on the host.

## 3. Launch prerequisites

| Dependency | Required state |
| --- | --- |
| Linux host account | The operator can create one host that meets the guide's minimum |
| Render account | The operator can create one Web Service that reads this caller repository |

Both must be true in the same sitting. They are the only blockers once section 1 is recorded.

## 4. Execution trigger

When section 3 is true, follow [Infrastructure Execution](INFRASTRUCTURE_EXECUTION.md) from the host. Create the SSH key in that sitting. `DEPLOY_ANALYTICS` stays unset until that chapter sets it, immediately before the one dispatch.

## 5. Success

The launch is complete when [Deployment Readiness](DEPLOYMENT_READINESS.md) section 3 is met and the recommended SHA equals the public core SHA that deploy checked out.

## 6. Deferred work

A VenueAdd row waits until this environment is successful on `venues: []`. The manifest stays empty through the first deploy.
