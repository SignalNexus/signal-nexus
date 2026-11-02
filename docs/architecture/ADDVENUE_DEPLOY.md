# AddVenue deployment

English is canonical. The Japanese mirror is [ADDVENUE_DEPLOY_JA.md](ADDVENUE_DEPLOY_JA.md).

The public core does not contain a paid venue package. The caller workflow passes the core commit, the manifest path, the SSH host, the SSH user, the core directory, and the venue directory. Those values are not stored in the shared workflow. When the manifest exists, the run installs only the commits named there.

## Manifest

One deployment target has one `venueadd/venues.yaml`. That path is outside the public export. The example shape is [venues.example.yaml](../../deploy/venueadd/venues.example.yaml).

A record has `import_name`, `repository`, `sha`, `venue_id`, and `requirements_file`. It does not name a Python version, a secret, a validation command, a deploy mode, an SSH target, or a service manager.

An empty file, or no file, installs no AddVenue package.

## Repository access

A paid venue repository stays private. The customer is an outside collaborator with Read on each purchased repository, and is not a member of the publishing organization. The customer creates one fine-grained personal access token. Its resource owner is the organization that owns the venue repositories. Its permission is Contents: Read. Repository access follows the repositories that customer can already read.

The token is stored only as a secret on that customer's deploy repository. The caller passes it as `venueadd_read_token`. Signal Nexus does not keep the token, and the public core does not contain it.

An empty manifest completes with no token. A manifest row whose repository the token cannot read fails `venueadd-install`. `analytics-deploy` restarts the Analytics API only after that job succeeds, so a failed fetch leaves the installed tree unchanged.

A refund removes the manifest row and runs deploy once. The apply step deletes a venue directory the manifest no longer names. The publisher then removes the Read grant. Removing Read while the row remains makes the next deploy fail before restart.

## Workflow split

`venueadd-install` checks out the pinned commits, solves one lock, and runs the production loader. It does not open an SSH session, write a service file, or restart a process.

`analytics-vm` is the caller for Customer #1. It passes repository variables and secrets into `analytics-deploy`. A failed lock or a failed loader skips the restart. The venue directory is the caller's `venue_directory` input.

## Dependency resolution

`uv` compiles Core `requirements.txt`, every venue `requirements_file` at its pinned commit, and [constraints.txt](../../deploy/venueadd/constraints.txt) in one solve. The constraint requires `urllib3==2.8.0`.

[exceptions.yml](../../deploy/venueadd/exceptions.yml) is the only override list. It currently drops the `urllib3` requirement declared by `lighter-sdk` 1.1.8. The package is installed without that declaration. The solved lock still contains `urllib3==2.8.0`. A venue manifest cannot add an override. If the combined requirements have no solution, the run stops before the environment variable or the restart.

## Rollback

Change the manifest `sha` to the previous commit and run `analytics-vm` again. The tree at `/opt/signal-nexus/venueadd/<import_name>/` is replaced by that commit. `uv pip sync` makes the virtual environment contain the lock and removes distributions that are not in it. The exception package is then installed without the dropped requirement. A newer dependency from the abandoned commit does not remain.

## What this run does not do

Venue API secrets stay in the environment files the Analytics API already loads. This workflow does not create those secrets. A new machine still needs them, in the same way it needs the Arcus and MEXC keys.

The workflow installs onto the host named by the caller's SSH input. It does not build a container image and it does not configure a second machine. Customer #1 must set `DEPLOY_ANALYTICS`, `ANALYTICS_SSH_USER`, `ANALYTICS_CORE_DIRECTORY`, and `ANALYTICS_VENUE_DIRECTORY` on the caller repository before the next run.
