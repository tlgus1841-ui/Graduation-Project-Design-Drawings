# ==============================================================================
# Self-Defending SDN Tower: Security Patch Server Container (10.0.0.253:80)
# Phase 6-C-1 Milestone
# ==============================================================================
FROM nginx:1.25-alpine

LABEL maintainer="Self-Defending SDN Tower Team"
LABEL description="Admin Zone dedicated physical patch/update server for quarantined hosts"

# Remove default nginx config and web assets
RUN rm -rf /etc/nginx/conf.d /usr/share/nginx/html/*

# Copy custom nginx configuration
COPY nginx.conf /etc/nginx/nginx.conf

# Copy patch scripts and landing index
RUN mkdir -p /usr/share/nginx/html/patches
COPY clean_agent.sh /usr/share/nginx/html/patches/clean_agent.sh
RUN chmod +x /usr/share/nginx/html/patches/clean_agent.sh

RUN echo '<html><head><title>SDN Tower Patch Server</title></head><body><h1>Admin Zone Patch Server (10.0.0.253)</h1><p>Available patches: <a href="/patches/clean_agent.sh">clean_agent.sh</a></p></body></html>' > /usr/share/nginx/html/index.html

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
