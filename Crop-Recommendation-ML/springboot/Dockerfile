FROM maven:3.9-eclipse-temurin-17 AS build
WORKDIR /workspace
COPY pom.xml .
COPY src ./src
RUN mvn -B clean package -DskipTests

FROM eclipse-temurin:17-jre
WORKDIR /app
COPY --from=build /workspace/target/smartcrop-springboot-1.0.0.jar /app/app.jar
EXPOSE 10000
CMD ["sh", "-c", "exec java -jar /app/app.jar --server.port=${PORT:-10000}"]
