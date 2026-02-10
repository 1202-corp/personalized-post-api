package handler

import "ppp/api/internal/config"

// Handler holds dependencies for HTTP handlers (config, services when added).
type Handler struct {
	Config *config.Config
}

// New returns a new Handler.
func New(cfg *config.Config) *Handler {
	return &Handler{Config: cfg}
}
