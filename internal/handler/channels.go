package handler

import (
	"net/http"
	"strconv"

	"ppp/api/internal/mock"
	"ppp/api/internal/response"
)

// ChannelsCreate handles POST /api/v1/channels.
func (h *Handler) ChannelsCreate(w http.ResponseWriter, r *http.Request) {
	if !h.Config.UseMock {
		response.NotImplemented(w)
		return
	}
	var body struct {
		TelegramID int64  `json:"telegram_id"`
		Username   string `json:"username,omitempty"`
		Title      string `json:"title"`
	}
	_ = decodeJSON(r, &body)
	if body.TelegramID == 0 {
		body.TelegramID = 123456789
	}
	ch := mock.ChannelByID(1)
	if hasField(r) {
		response.JSON(w, http.StatusCreated, ch)
		return
	}
	response.NoContent(w)
}

// ChannelsList handles GET /api/v1/channels.
func (h *Handler) ChannelsList(w http.ResponseWriter, r *http.Request) {
	if !h.Config.UseMock {
		response.NotImplemented(w)
		return
	}
	defaults := r.URL.Query().Get("defaults") == "true"
	list := mock.ChannelsList(defaults)
	response.JSON(w, http.StatusOK, list)
}

// ChannelsGet handles GET /api/v1/channels/{channel_id}.
func (h *Handler) ChannelsGet(w http.ResponseWriter, r *http.Request, channelID int64) {
	if !h.Config.UseMock {
		response.NotImplemented(w)
		return
	}
	response.JSON(w, http.StatusOK, mock.ChannelByID(channelID))
}

// ChannelsUserAdd handles POST /api/v1/channels/user.
func (h *Handler) ChannelsUserAdd(w http.ResponseWriter, r *http.Request) {
	if !h.Config.UseMock {
		response.NotImplemented(w)
		return
	}
	var body struct {
		TelegramID int64 `json:"telegram_id"`
		ChannelID  int64 `json:"channel_id"`
	}
	_ = decodeJSON(r, &body)
	if hasField(r) {
		response.JSON(w, http.StatusCreated, mock.ChannelByID(body.ChannelID))
		return
	}
	response.NoContent(w)
}

// ChannelsUserList handles GET /api/v1/channels/user/{telegram_id}.
func (h *Handler) ChannelsUserList(w http.ResponseWriter, r *http.Request, telegramID int64) {
	if !h.Config.UseMock {
		response.NotImplemented(w)
		return
	}
	response.JSON(w, http.StatusOK, mock.ChannelsUser(telegramID))
}

func parseChannelID(s string) (int64, bool) {
	id, err := strconv.ParseInt(s, 10, 64)
	return id, err == nil
}
