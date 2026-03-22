.PHONY: up down logs restart clean

# Start the application in detached mode
up:
	docker compose up --build -d

# Stop the application and remove containers
down:
	docker compose down

# Stop the application and remove volumes (erases database data)
clean:
	docker compose down -v

# View logs for all services
logs:
	docker compose logs -f

# Restart all services
restart:
	docker compose restart
