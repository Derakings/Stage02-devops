#!/bin/bash

# Clean and build fresh containers
docker-compose down -v

docker-compose up -d

sleep 10

docker-compose ps


# Test the nodejs services through the Nginx proxy
echo " Blue Active"
curl -i http://localhost:8080/version | grep -E "HTTP|X-App-Pool|X-Release-Id"

# Test 2: Trigger chaos
echo -e "\nTest 2: Breaking Blue"
curl -X POST "http://localhost:8081/chaos/start?mode=error"

# Test 3: Verify switch to Green
echo -e "\nTest 3: Switched to Green"
sleep 2
curl -i http://localhost:8080/version | grep -E "HTTP|X-App-Pool|X-Release-Id"

# Test 4: Multiple requests (all should be Green & 200)
echo -e "\nTest 4: 10 Consecutive Requests"
for i in {1..10}; do
  STATUS=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:8080/version)
  POOL=$(curl -s -I http://localhost:8080/version | grep "X-App-Pool" | awk '{print $2}' | tr -d '\r')
  echo "Request $i: Status=$STATUS Pool=$POOL"
done

# Test 5: Restore Blue
echo -e "\nTest 5: Restoring Blue"
curl -X POST "http://localhost:8081/chaos/stop"
echo "Waiting 12 seconds for Blue to recover..."
sleep 12

# Test 6: Verify back to Blue
echo -e "\nTest 6: Back to Blue"
curl -i http://localhost:8080/version | grep -E "HTTP|X-App-Pool|X-Release-Id"
