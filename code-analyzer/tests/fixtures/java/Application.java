package com.example.application;

import java.util.List;
import java.util.ArrayList;
import java.util.Map;
import java.util.HashMap;

import com.example.models.User;
import com.example.services.AuthService;
import com.example.repositories.UserRepository;
import static java.util.Collections.emptyList;
import com.example.config.AppConfig;

public class Application {

    private final UserRepository userRepository;
    private final AuthService authService;
    private final AppConfig config;

    public Application(AppConfig config) {
        this.config = config;
        this.userRepository = new UserRepository(config.getDatabaseUrl());
        this.authService = new AuthService(userRepository);
    }

    public User login(String username, String password) {
        return authService.authenticate(username, password);
    }

    public List<User> getAllUsers() {
        return userRepository.findAll();
    }

    public static void main(String[] args) {
        AppConfig config = AppConfig.fromArgs(args);
        Application app = new Application(config);
        app.run();
    }

    public void run() {
        System.out.println("Application started");
    }
}