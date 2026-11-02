# Venue License and Repository Access

English is canonical. The Japanese mirror is [VENUE_LICENSE_JA.md](VENUE_LICENSE_JA.md).

This chapter is the public license and access model for one paid venue. The deploy layout is [AddVenue deployment](../architecture/ADDVENUE_DEPLOY.md). The first-health path does not require a venue. [Community Deployment Guide](../COMMUNITY_DEPLOYMENT_GUIDE.md) leaves `venues: []` until a purchase. This chapter does not add a required fact for that path.

## 1. What a purchase is

VenueAdd is the extension for one venue, including later maintenance of that same venue. It is not a right to every later venue. It does not include Starter, Volume Pack, or Profit Pack.

The public core does not contain a paid venue package.

## 2. Manifest

One environment has one `venueadd/venues.yaml`. A record has `import_name`, `repository`, `sha`, `venue_id`, and `requirements_file`. It does not name a Python version, a secret, a validation command, a deploy mode, an SSH target, or a service manager.

An empty file, or `venues: []`, installs no package and does not require a token.

## 3. Repository access

A paid venue repository stays private. The operator of the caller repository is an outside collaborator with Read on each purchased repository, and is not a member of the publishing organization.

That operator creates one fine-grained personal access token. Its resource owner is the organization that owns the venue repositories. Its permission is Contents: Read. Repository access follows the repositories that operator can already read.

The token is stored only as `VENUEADD_READ_TOKEN` on that caller repository. The public core does not contain it. Signal Nexus does not keep a copy.

## 4. Fetch

The caller workflow passes the token as `venueadd_read_token`. A row whose repository the token cannot read fails `venueadd-install`. `analytics-deploy` restarts the Analytics API only after that job succeeds, so a failed fetch leaves the installed tree unchanged.

An empty manifest returns before git.

## 5. Refund

Remove the manifest row and run deploy once. The apply step deletes a venue directory the manifest no longer names. The publisher then removes the Read grant. Removing Read while the row remains makes the next deploy fail before restart.
