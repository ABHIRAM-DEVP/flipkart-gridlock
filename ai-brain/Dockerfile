FROM python:3.11-slim

WORKDIR /app

# Add this line to create the missing output folder
RUN mkdir -p artifacts

COPY requirements.txt .
# Retry pip install to avoid transient network timeouts (3 attempts, 120s timeout)
RUN set -eux \
	&& for i in 1 2 3; do \
		pip install --no-cache-dir --timeout 120 -r requirements.txt && break || \
		(echo "pip install failed, retrying ($i)" && sleep 5); \
	done

COPY . .
RUN chmod +x /app/docker-entrypoint.sh

EXPOSE 8000

CMD ["sh", "/app/docker-entrypoint.sh"]
