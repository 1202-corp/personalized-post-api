package config

import (
	"os"
	"strconv"
	"strings"
)

// Config holds application configuration from environment.
type Config struct {
	Port                   int
	UseMock                bool
	DatabaseURL            string
	RedisURL               string
	MLServiceURL           string
	DefaultTrainingChannels string
	JWTSecret              string
	JWTAccessExpireMinutes int
	JWTRefreshExpireDays   int
	AdminUsername          string
	AdminPassword          string
}

// Load reads configuration from environment. Call godotenv.Load() in main before Load if using .env file.
func Load() *Config {
	return &Config{
		Port:                   getIntEnv("PORT", 8000),
		UseMock:                getBoolEnv("USE_MOCK", true),
		DatabaseURL:            getEnv("DATABASE_URL", ""),
		RedisURL:               getEnv("REDIS_URL", "redis://localhost:6379/0"),
		MLServiceURL:           getEnv("ML_SERVICE_URL", "http://localhost:8002"),
		DefaultTrainingChannels: getEnv("DEFAULT_TRAINING_CHANNELS", "@durov,@telegram"),
		JWTSecret:              getEnv("JWT_SECRET", ""),
		JWTAccessExpireMinutes: getIntEnv("JWT_ACCESS_TOKEN_EXPIRE_MINUTES", 1440),
		JWTRefreshExpireDays:   getIntEnv("JWT_REFRESH_TOKEN_EXPIRE_DAYS", 7),
		AdminUsername:          getEnv("ADMIN_USERNAME", "admin"),
		AdminPassword:          getEnv("ADMIN_PASSWORD", ""),
	}
}

func getEnv(key, defaultVal string) string {
	if v := os.Getenv(key); v != "" {
		return v
	}
	return defaultVal
}

func getIntEnv(key string, defaultVal int) int {
	if v := os.Getenv(key); v != "" {
		if n, err := strconv.Atoi(v); err == nil {
			return n
		}
	}
	return defaultVal
}

func getBoolEnv(key string, defaultVal bool) bool {
	v := strings.ToLower(strings.TrimSpace(os.Getenv(key)))
	switch v {
	case "true", "1", "on":
		return true
	case "false", "0", "off":
		return false
	}
	return defaultVal
}
