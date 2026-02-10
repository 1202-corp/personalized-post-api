package handler

import (
	"net/http"

	"ppp/api/internal/mock"
	"ppp/api/internal/response"
)

// MLTrain handles POST /api/v1/ml/train.
func (h *Handler) MLTrain(w http.ResponseWriter, r *http.Request) {
	if !h.Config.UseMock {
		response.NotImplemented(w)
		return
	}
	var body struct {
		TelegramID int64 `json:"telegram_id"`
	}
	_ = decodeJSON(r, &body)
	response.JSON(w, http.StatusOK, mock.MLTrain())
}
