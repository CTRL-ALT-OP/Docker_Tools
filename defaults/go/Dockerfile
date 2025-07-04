FROM docker.io/library/golang:1.24.4-alpine3.22@sha256:68932fa6d4d4059845c8f40ad7e654e626f3ebd3706eef7846f319293ab5cb7a

RUN apk add --no-cache git

# Grab dependency metadata, the * makes the file optional
COPY go.mod go.sum* ./
RUN go mod download

# Copy source 
COPY . .

CMD ["sh"]
