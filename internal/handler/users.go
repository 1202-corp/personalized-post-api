package handler

import (
	"net/http"
	"strconv"

	"ppp/api/internal/mock"
	"ppp/api/internal/response"
)

// UsersCreate handles POST /api/v1/users.
func (h *Handler) UsersCreate(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		response.NotFound(w, "method not allowed")
		return
	}
	if !h.Config.UseMock {
		response.NotImplemented(w)
		return
	}
	// Mock: accept body with telegram_id or use default
	var body struct {
		TelegramID int64  `json:"telegram_id"`
		Username   string `json:"username,omitempty"`
		FirstName  string `json:"first_name,omitempty"`
		LastName   string `json:"last_name,omitempty"`
	}
	_ = decodeJSON(r, &body)
	if body.TelegramID == 0 {
		body.TelegramID = 123456789
	}
	user := mock.UserCreate(body.TelegramID)
	if hasField(r) {
		response.JSON(w, http.StatusCreated, user)
		return
	}
	response.NoContent(w)
}

// UsersGet handles GET /api/v1/users/{telegram_id}.
func (h *Handler) UsersGet(w http.ResponseWriter, r *http.Request, telegramID int64) {
	if !h.Config.UseMock {
		response.NotImplemented(w)
		return
	}
	response.JSON(w, http.StatusOK, mock.UserByTelegramID(telegramID))
}

// UsersPatch handles PATCH /api/v1/users/{telegram_id}.
func (h *Handler) UsersPatch(w http.ResponseWriter, r *http.Request, telegramID int64) {
	if !h.Config.UseMock {
		response.NotImplemented(w)
		return
	}
	if hasField(r) {
		response.JSON(w, http.StatusOK, mock.UserByTelegramID(telegramID))
		return
	}
	response.NoContent(w)
}

// UsersDelete handles DELETE /api/v1/users/{telegram_id}.
func (h *Handler) UsersDelete(w http.ResponseWriter, r *http.Request, telegramID int64) {
	if !h.Config.UseMock {
		response.NotImplemented(w)
		return
	}
	response.NoContent(w)
}

func parseTelegramID(s string) (int64, bool) {
	id, err := strconv.ParseInt(s, 10, 64)
	return id, err == nil
}
