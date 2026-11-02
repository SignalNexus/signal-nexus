# AddVenue Operations

English is canonical. The Japanese mirror is [ADDVENUE_OPERATIONS_JA.md](ADDVENUE_OPERATIONS_JA.md).

This chapter is the public procedure for adding one manifest row after an environment is already successful on `venues: []`. The license model is [Venue License](VENUE_LICENSE.md). The workflow layout is [AddVenue deployment](../architecture/ADDVENUE_DEPLOY.md). This chapter does not add a required fact to the Community Deployment Guide's first-health path.

Lighter is a worked case. It is not a required install. txflow is not introduced here.

## 1. When this chapter starts

The environment has a last successful deploy. The recommended SHA is set. `venueadd/venues.yaml` is still `venues: []`. `VENUEADD_READ_TOKEN` is still unset. `SIGNAL_NEXUS_VENUEADD` is unset.

Do not add a row during [Customer Creation](CUSTOMER_CREATION.md) or the first [Launch Gate](LAUNCH_GATE.md).

## 2. One row

1. Receive Read on the purchased venue repository.
2. Create the fine-grained token in [Venue License](VENUE_LICENSE.md) section 3.
3. Store it as `VENUEADD_READ_TOKEN` on this caller repository.
4. Add one record to `venueadd/venues.yaml`: `import_name`, `repository`, `sha`, `venue_id`, `requirements_file`.
5. Place any venue API secrets in the environment files the Analytics API already loads. The workflow does not create those secrets.
6. Run `workflow_dispatch` once.
7. Repeat the health checks in [Deployment Readiness](DEPLOYMENT_READINESS.md). The log now names that venue repository. `SIGNAL_NEXUS_VENUEADD` may be set by the install.

One row is one venue. A second purchase is a second row and a second Read grant.

## 3. Lighter as a worked case

When the purchased package is lighter, the record uses that package's `import_name`, repository, commit, `venue_id`, and `requirements_file` from its SETUP. The fetch uses the credential helper and username `x-access-token`. Those details are [Troubleshooting](TROUBLESHOOTING.md).

This chapter does not require lighter. An environment that never purchases a venue stays on `venues: []`.

## 4. What this chapter does not do

It does not introduce txflow. It does not tell the operator to install a venue to reach health validation. Package files stay in the AddVenue package: LICENSE, README, SETUP, RELEASE_NOTES.
