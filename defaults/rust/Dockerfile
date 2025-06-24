FROM docker.io/library/rust:1.87.0-bullseye@sha256:8c28ce7ffd6f2d49fdb34fe463740bdd8e5d802bb3a7bf92f0132b371564497b
WORKDIR /app
COPY . .
RUN cargo build
CMD ["sh"]
