# Build phase (Node 24 LTS: Angular 21 requires ^20.19, ^22.12 or >=24)
FROM node:24.22.0-alpine AS build

# Built from the repository root (docker-compose: context ".", dockerfile
# soup-app/Dockerfile): the app compiles @soup/sdk from ../soup-packages/sdk
# (tsconfig.json "paths"), so the layout mirrors the repository.
WORKDIR /usr/src/soup-app

# Copy the package.json and package-lock.json files to install dependencies
COPY soup-app/package*.json ./

# Install exactly the versions of package-lock.json (the Angular CLI included)
RUN npm ci

# Copy the rest of the application code and the SDK of the packages
COPY soup-app/ .
COPY soup-packages/sdk/ /usr/src/soup-packages/sdk/

# Run npm linting
RUN npm run lint

# Build the Angular application in production mode, with the CLI of the project
RUN npx ng build --configuration production

# Deploy phase with Nginx
FROM nginx:alpine

# Remove the nginx file html
RUN rm -rf /usr/share/nginx/html

# Copy the Nginx configuration file
COPY soup-app/nginx.conf /etc/nginx/nginx.conf

# Copy the static build files from the build phase to Nginx's serving directory
COPY --from=build /usr/src/soup-app/dist/soup-app/browser /usr/share/nginx/html

# Expose port 80 for Nginx
EXPOSE 80

# Run Nginx in the foreground (necessary for the container to keep running)
CMD ["nginx", "-g", "daemon off;"]