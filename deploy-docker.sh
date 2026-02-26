#!/bin/bash
# SCADA Simulator Docker Deployment Script

set -e

echo "========================================"
echo "SCADA Simulator - Docker Deployment"
echo "========================================"
echo ""

# Check if Docker is installed
if ! command -v docker &> /dev/null; then
    echo "❌ Error: Docker is not installed"
    echo "Please install Docker: https://docs.docker.com/get-docker/"
    exit 1
fi

# Check if Docker Compose is available
if ! docker compose version &> /dev/null; then
    echo "❌ Error: Docker Compose is not available"
    echo "Please install Docker Compose: https://docs.docker.com/compose/install/"
    exit 1
fi

echo "✓ Docker is installed"
echo "✓ Docker Compose is available"
echo ""

# Function to show usage
show_usage() {
    echo "Usage: ./deploy-docker.sh [COMMAND]"
    echo ""
    echo "Commands:"
    echo "  build       - Build Docker images"
    echo "  up          - Start all services"
    echo "  down        - Stop all services"
    echo "  restart     - Restart all services"
    echo "  logs        - Show logs from all services"
    echo "  status      - Show status of services"
    echo "  clean       - Remove containers and volumes"
    echo "  test        - Run tests in container"
    echo "  dashboard   - Open web dashboard in browser"
    echo ""
}

# Parse command
COMMAND=${1:-up}

case $COMMAND in
    build)
        echo "Building Docker images..."
        docker compose build
        echo "✓ Build complete"
        ;;
    
    up)
        echo "Starting SCADA Simulator..."
        docker compose up -d
        echo ""
        echo "✓ Services started"
        echo ""
        echo "Access points:"
        echo "  - Web Dashboard:    http://localhost:8501 (login: admin/admin123)"
        echo "  - API Server:       http://localhost:8000/docs"
        echo "  - Modbus TCP:       localhost:502"
        echo "  - IEC 104:          localhost:2404"
        echo "  - TimescaleDB:      localhost:5432"
        echo "  - Secure Master:    localhost:8080"
        echo ""
        echo "Quick commands:"
        echo "  ./deploy-docker.sh dashboard  - Open web dashboard in browser"
        echo "  ./deploy-docker.sh logs       - View service logs"
        echo "  ./deploy-docker.sh status     - Check service status"
        echo ""
        ;;
    
    down)
        echo "Stopping SCADA Simulator..."
        docker compose down
        echo "✓ Services stopped"
        ;;
    
    restart)
        echo "Restarting SCADA Simulator..."
        docker compose restart
        echo "✓ Services restarted"
        ;;
    
    logs)
        echo "Showing logs (Ctrl+C to exit)..."
        docker compose logs -f
        ;;
    
    status)
        echo "Service Status:"
        echo ""
        docker compose ps
        echo ""
        echo "Network Status:"
        docker network inspect scada_sim_scada_network --format='{{.Name}}: {{len .Containers}} containers' 2>/dev/null || echo "Network not created"
        ;;
    
    clean)
        echo "⚠️  WARNING: This will remove all containers, networks, and volumes!"
        read -p "Are you sure? (yes/no): " confirm
        if [ "$confirm" = "yes" ]; then
            echo "Cleaning up..."
            docker compose down -v
            docker volume rm scada_sim_timescale_data scada_sim_audit_logs 2>/dev/null || true
            echo "✓ Cleanup complete"
        else
            echo "Cleanup cancelled"
        fi
        ;;
    
    test)
        echo "Running tests in container..."
        docker compose run --rm simulator python3 run_tests.py
        ;;
    
    dashboard)
        echo "Opening web dashboard in browser..."
        # Try different browser commands based on OS
        if command -v xdg-open &> /dev/null; then
            xdg-open http://localhost:8501
        elif command -v open &> /dev/null; then
            open http://localhost:8501
        elif command -v start &> /dev/null; then
            start http://localhost:8501
        else
            echo "Dashboard URL: http://localhost:8501"
            echo "Please open this URL in your browser"
        fi
        ;;
    
    help|--help|-h)
        show_usage
        ;;
    
    *)
        echo "❌ Unknown command: $COMMAND"
        echo ""
        show_usage
        exit 1
        ;;
esac
