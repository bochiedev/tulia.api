# Deployment Checklist

Use this checklist for production deployments to ensure nothing is missed.

## Pre-Deployment Phase

### Code Review
- [ ] All code changes reviewed and approved
- [ ] All tests passing (unit, integration, E2E)
- [ ] No critical or high-severity security vulnerabilities
- [ ] Code coverage meets minimum threshold (>80%)
- [ ] Linting and formatting checks pass
- [ ] No TODO or FIXME comments in production code

### Database
- [ ] All migrations reviewed and tested
- [ ] Migration SQL reviewed for performance impact
- [ ] Estimated migration duration documented
- [ ] Rollback plan documented
- [ ] Database backup created and verified
- [ ] Backup restoration tested
- [ ] Migration tested on staging with production-like data

### Configuration
- [ ] All environment variables documented
- [ ] Production environment variables configured
- [ ] Secrets rotated (if needed)
- [ ] `DEBUG=False` in production
- [ ] `SECRET_KEY` is unique and secure
- [ ] `ENCRYPTION_KEY` generated and stored securely
- [ ] `ALLOWED_HOSTS` configured correctly
- [ ] CORS origins configured
- [ ] Email service configured and tested
- [ ] Sentry DSN configured
- [ ] OpenAI/Anthropic API key configured

### Infrastructure
- [ ] Server resources adequate (CPU, RAM, disk)
- [ ] Database connection pool sized appropriately
- [ ] Redis memory limit configured
- [ ] Celery worker concurrency configured
- [ ] SSL/TLS certificates valid and installed
- [ ] Firewall rules configured
- [ ] Load balancer configured (if applicable)
- [ ] CDN configured (if applicable)
- [ ] DNS records updated (if needed)

### Monitoring & Alerting
- [ ] Sentry configured and tested
- [ ] Health check endpoint verified
- [ ] Uptime monitoring configured (UptimeRobot, Pingdom, etc.)
- [ ] Log aggregation configured
- [ ] Alerting rules configured
- [ ] PagerDuty/on-call rotation configured
- [ ] Slack notifications configured
- [ ] Dashboard created (Grafana, Datadog, etc.)

### Documentation
- [ ] Deployment documentation updated
- [ ] API documentation updated
- [ ] Changelog updated
- [ ] Release notes prepared
- [ ] Runbooks updated
- [ ] Architecture diagrams updated (if changed)

### Communication
- [ ] Stakeholders notified of deployment schedule
- [ ] Maintenance window scheduled (if needed)
- [ ] Customer communication prepared (if downtime expected)
- [ ] Team availability confirmed
- [ ] Rollback plan communicated

### Testing
- [ ] Staging deployment successful
- [ ] Smoke tests passed on staging
- [ ] Performance testing completed
- [ ] Load testing completed (if significant changes)
- [ ] Security testing completed
- [ ] User acceptance testing completed

---

## Deployment Phase

### Pre-Deployment
- [ ] Maintenance mode enabled (if needed)
- [ ] Final database backup created
- [ ] Backup verified and accessible
- [ ] Current application version tagged in Git
- [ ] Deployment start time recorded

### Code Deployment
- [ ] Latest code pulled from repository
- [ ] Git tag/commit verified
- [ ] Dependencies installed/updated
- [ ] Static files collected
- [ ] File permissions verified

### Database Migration
- [ ] Celery workers stopped (if schema changes affect tasks)
- [ ] Database migrations applied
- [ ] Migration success verified
- [ ] Migration duration recorded
- [ ] Data integrity checks passed

### Service Restart
- [ ] Web servers restarted
- [ ] Celery workers restarted
- [ ] Celery beat restarted
- [ ] All services healthy

### Verification
- [ ] Health check endpoint returns 200
- [ ] All service dependencies healthy (database, Redis, Celery)
- [ ] No errors in application logs
- [ ] No errors in Sentry
- [ ] Critical endpoints responding correctly
- [ ] Response times within acceptable range

### Smoke Testing
- [ ] User authentication works
- [ ] Tenant context resolution works
- [ ] RBAC permissions enforced correctly
- [ ] Webhook processing works
- [ ] Message sending works
- [ ] Order creation works
- [ ] Appointment booking works
- [ ] Analytics endpoints work
- [ ] Admin endpoints work (if applicable)

---

## Post-Deployment Phase

### Monitoring (First 15 Minutes)
- [ ] Error rate normal (<1%)
- [ ] Response times normal (p95 <2s)
- [ ] No spike in 5xx errors
- [ ] No database connection errors
- [ ] No Redis connection errors
- [ ] Celery workers processing tasks
- [ ] No critical Sentry alerts

### Monitoring (First Hour)
- [ ] Application logs reviewed
- [ ] Sentry dashboard reviewed
- [ ] No unusual error patterns
- [ ] Performance metrics stable
- [ ] Database query performance normal
- [ ] Celery queue lengths normal
- [ ] Memory usage stable
- [ ] CPU usage stable

### Monitoring (First 24 Hours)
- [ ] Daily metrics reviewed
- [ ] User feedback reviewed
- [ ] Support tickets reviewed
- [ ] No critical issues reported
- [ ] Performance trends normal

### Cleanup
- [ ] Maintenance mode disabled
- [ ] Old code versions archived
- [ ] Old log files archived
- [ ] Temporary files cleaned up

### Documentation
- [ ] Deployment recorded in changelog
- [ ] Release notes published
- [ ] Stakeholders notified of completion
- [ ] Team debriefed
- [ ] Lessons learned documented

### Git
- [ ] Deployment tagged in Git
- [ ] Tag pushed to remote
- [ ] Release created on GitHub/GitLab
- [ ] Sentry release created

---

## Rollback Checklist

Use this if deployment needs to be rolled back.

### Decision
- [ ] Rollback decision made by authorized person
- [ ] Rollback reason documented
- [ ] Stakeholders notified

### Preparation
- [ ] Previous version identified
- [ ] Database backup from before deployment available
- [ ] Rollback plan reviewed

### Execution
- [ ] Maintenance mode enabled
- [ ] Application stopped
- [ ] Code reverted to previous version
- [ ] Database rolled back (if needed)
- [ ] Dependencies reverted (if needed)
- [ ] Application restarted
- [ ] Health checks verified

### Verification
- [ ] Application functioning correctly
- [ ] No errors in logs
- [ ] Critical user flows tested
- [ ] Stakeholders notified of rollback completion

### Post-Rollback
- [ ] Root cause analysis initiated
- [ ] Fix planned
- [ ] Re-deployment scheduled
- [ ] Lessons learned documented

---

## Environment-Specific Checklists

### Staging Deployment
- [ ] Staging environment matches production configuration
- [ ] Test data loaded
- [ ] All integration tests passed
- [ ] Performance acceptable
- [ ] No critical issues found

### Production Deployment
- [ ] All staging checks passed
- [ ] Production backup created
- [ ] Maintenance window scheduled (if needed)
- [ ] On-call engineer available
- [ ] Rollback plan ready

---

## Special Deployment Scenarios

### Database Schema Changes
- [ ] Migration tested with production-like data volume
- [ ] Migration duration estimated
- [ ] Downtime communicated (if required)
- [ ] Rollback tested
- [ ] Indexes created concurrently (PostgreSQL)
- [ ] Large data migrations split into batches

### Breaking API Changes
- [ ] API versioning implemented
- [ ] Deprecation notices sent
- [ ] Migration guide provided
- [ ] Backward compatibility maintained (if possible)
- [ ] Client applications updated

### Infrastructure Changes
- [ ] Infrastructure changes tested in staging
- [ ] Capacity planning completed
- [ ] Scaling strategy documented
- [ ] Monitoring updated for new infrastructure
- [ ] Disaster recovery plan updated

### Security Updates
- [ ] Security patch tested
- [ ] Impact assessment completed
- [ ] Expedited deployment approved (if critical)
- [ ] Security advisory published (if applicable)
- [ ] Affected users notified (if applicable)

---

## Deployment Metrics

Track these metrics for each deployment:

- **Deployment Duration**: Start to completion time
- **Downtime**: Total downtime (if any)
- **Migration Duration**: Database migration time
- **Rollback Count**: Number of rollbacks
- **Issues Found**: Post-deployment issues
- **Time to Resolution**: Time to fix issues
- **Success Rate**: Successful deployments / total deployments

---

## Sign-Off

### Pre-Deployment Sign-Off
- [ ] Tech Lead: _____________________ Date: _____
- [ ] DevOps Lead: ___________________ Date: _____
- [ ] Product Owner: _________________ Date: _____

### Post-Deployment Sign-Off
- [ ] Deployment Engineer: ___________ Date: _____
- [ ] QA Lead: ______________________ Date: _____
- [ ] Tech Lead: _____________________ Date: _____

---

## Notes

Use this section for deployment-specific notes:

```
Deployment Date: _______________
Version: _______________
Deployed By: _______________

Notes:
- 
- 
- 

Issues Encountered:
- 
- 
- 

Resolutions:
- 
- 
- 
```

---

## Quick Reference

### Critical Commands

```bash
# Health check
curl https://api.yourdomain.com/v1/health

# View logs
docker-compose logs -f web
sudo journalctl -u tulia-web -f

# Restart services
docker-compose restart web celery_worker
sudo systemctl restart tulia-web tulia-celery-worker

# Database backup
pg_dump -U tulia_user tulia_db > backup_$(date +%Y%m%d_%H%M%S).sql

# Database restore
psql -U tulia_user tulia_db < backup_20250112_120000.sql

# Run migrations
python manage.py migrate

# Rollback migration
python manage.py migrate app_name previous_migration_number
```

### Emergency Contacts

- **On-Call Engineer**: [Phone/Slack]
- **Tech Lead**: [Phone/Slack]
- **DevOps Lead**: [Phone/Slack]
- **Product Owner**: [Phone/Slack]

### Important URLs

- **Production**: https://api.yourdomain.com
- **Staging**: https://staging-api.yourdomain.com
- **Sentry**: https://sentry.io/organizations/your-org/projects/tulia-ai/
- **Monitoring**: [Your monitoring dashboard URL]
- **Status Page**: [Your status page URL]

---

**Last Updated**: 2025-01-12
**Version**: 1.0.0
