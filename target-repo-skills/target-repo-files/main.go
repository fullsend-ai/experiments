package main

import (
	"log"
	"net/http"

	"github.com/example/userapi/handlers"
)

func main() {
	mux := http.NewServeMux()
	mux.HandleFunc("GET /health", handlers.Health)
	mux.HandleFunc("GET /users", handlers.ListUsers)
	mux.HandleFunc("GET /users/{id}", handlers.GetUser)
	mux.HandleFunc("POST /users", handlers.CreateUser)

	log.Println("listening on :8080")
	log.Fatal(http.ListenAndServe(":8080", mux))
}