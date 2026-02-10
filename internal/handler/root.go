package handler

import (
	"net/http"

	"ppp/api/internal/mock"
	"ppp/api/internal/response"
)

// Root returns GET / handler.
func (h *Handler) Root(w http.ResponseWriter, r *http.Request) {
	response.JSON(w, http.StatusOK, mock.Root())
}

// Health returns GET /health handler.
func (h *Handler) Health(w http.ResponseWriter, r *http.Request) {
	w.WriteHeader(http.StatusOK)
	_, _ = w.Write([]byte("ok"))
}
