package main

import (
	"fmt"
	"os"

	"myproject/logger"
	"myproject/models"
	"myproject/services"
)

type Server struct {
	Host string
	Port int
}

type Config interface {
	Load() error
}

func NewServer(host string, port int) *Server {
	return &Server{Host: host, Port: port}
}

func (s *Server) Start() error {
	logger.Info("server starting", "host", s.Host)
	fmt.Println("Server started")
	return nil
}

func main() {
	srv := services.CreateDefaultServer()
	srv.Start()
	_ = os.Getenv("HOME")
}