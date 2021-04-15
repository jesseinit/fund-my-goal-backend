SHELL := /bin/bash

up-prod:
	@ echo 'Starting Production Environment Docker Containers'
	@ docker-compose -f dc.prod.yml up --build -d

down-prod:
	@ echo 'Stopping Production Environment Docker Containers'
	@ docker-compose -f dc.prod.yml down

restart-prod:
	@ echo 'Restarting Production Environment Docker Containers'
	@ docker-compose -f dc.prod.yml restart

up-staging:
	@ echo 'Starting Staging Environment Docker Containers'
	@ docker-compose -f dc.staging.yml up --build -d

down-staging:
	@ echo 'Stoping Staging Environment Docker Containers'
	@ docker-compose -f dc.staging.yml down

restart-staging:
	@ echo 'Restarting Staging Environment Docker Containers'
	@ docker-compose -f dc.staging.yml restart

up-local:
	@ echo 'Starting Local Environment Docker Containers'
	@ docker-compose -f dc.local.yml up

down-local:
	@ echo 'Stopping Local Environment Docker Containers'
	@ docker-compose -f dc.local.yml down

restart-local:
	@ echo 'Restarting Local Environment Docker Containers'
	@ docker-compose -f dc.local.yml restart

tests-local:
	@ echo 'Running Container Tests'
	@ docker-compose -f dc.local.yml run tudo-api pytest
