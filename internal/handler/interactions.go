package handler

import (
	"net/http"
	"strconv"

	"ppp/api/internal/mock"
	"ppp/api/internal/response"
)

// InteractionsCreate handles POST /api/v1/interactions.
func (h *Handler) InteractionsCreate(w http.ResponseWriter, r *http.Request) {
	if !h.Config.UseMock {
		response.NotImplemented(w)
		return
	}
	var body struct {
		TelegramID       int64  `json:"telegram_id"`
		PostID           int64  `json:"post_id"`
		InteractionType  string `json:"interaction_type"`
	}
	_ = decodeJSON(r, &body)
	if hasField(r) {
		response.JSON(w, http.StatusCreated, mock.InteractionsList(body.TelegramID)[0])
		return
	}
	response.NoContent(w)
}

// InteractionsList handles GET /api/v1/interactions/{telegram_id}.
func (h *Handler) InteractionsList(w http.ResponseWriter, r *http.Request, telegramID int64) {
	if !h.Config.UseMock {
		response.NotImplemented(w)
		return
	}
	response.JSON(w, http.StatusOK, mock.InteractionsList(telegramID))
}

// InteractionsDelete handles DELETE /api/v1/interactions/{telegram_id}.
func (h *Handler) InteractionsDelete(w http.ResponseWriter, r *http.Request, telegramID int64) {
	if !h.Config.UseMock {
		response.NotImplemented(w)
		return
	}
	response.NoContent(w)
}

func parseUserID(s string) (int64, bool) {
	id, err := strconv.ParseInt(s, 10, 64)
	return id, err == nil
}
