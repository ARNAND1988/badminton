FROM node:20-bookworm-slim

ENV NODE_ENV=production

WORKDIR /app

COPY package.json ./
RUN npm install --omit=dev

COPY server.js ./

EXPOSE 3000

CMD ["npm", "start"]
