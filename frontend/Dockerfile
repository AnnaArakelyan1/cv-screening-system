FROM node:20-alpine

WORKDIR /app

COPY package*.json ./
RUN npm install
RUN npm install axios react-router-dom

COPY . .

EXPOSE 3000

CMD ["npm", "start"]