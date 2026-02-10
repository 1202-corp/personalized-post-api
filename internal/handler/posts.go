package handler

import (
	"net/http"
	"strconv"

	"ppp/api/internal/mock"
	"ppp/api/internal/response"
)

// PostsCreate handles POST /api/v1/posts.
func (h *Handler) PostsCreate(w http.ResponseWriter, r *http.Request) {
	if !h.Config.UseMock {
		response.NotImplemented(w)
		return
	}
	var body mock.PostsCreateRequest
	if err := decodeJSON(r, &body); err != nil {
		response.BadRequest(w, "invalid body")
		return
	}
	count := len(body.Posts)
	if count == 0 {
		count = 1
	}
	resp := mock.PostsCreate(count)
	response.JSON(w, http.StatusCreated, resp)
}

// PostsGet handles GET /api/v1/posts/{post_id}.
func (h *Handler) PostsGet(w http.ResponseWriter, r *http.Request, postID int64) {
	if !h.Config.UseMock {
		response.NotImplemented(w)
		return
	}
	response.JSON(w, http.StatusOK, mock.PostByID(postID))
}

// PostsContent handles GET /api/v1/posts/{post_id}/content.
func (h *Handler) PostsContent(w http.ResponseWriter, r *http.Request, postID int64) {
	if !h.Config.UseMock {
		response.NotImplemented(w)
		return
	}
	response.JSON(w, http.StatusOK, mock.PostContentByID(postID))
}

// PostsTraining handles POST /api/v1/posts/training.
func (h *Handler) PostsTraining(w http.ResponseWriter, r *http.Request) {
	if !h.Config.UseMock {
		response.NotImplemented(w)
		return
	}
	var body mock.PostsTrainingRequest
	if err := decodeJSON(r, &body); err != nil {
		response.BadRequest(w, "invalid body")
		return
	}
	if body.PostsPerChannel <= 0 {
		body.PostsPerChannel = 5
	}
	if len(body.ChannelIDs) == 0 {
		body.ChannelIDs = []int64{1, 2}
	}
	list := mock.PostsTraining(body.TelegramID, body.ChannelIDs, body.PostsPerChannel)
	response.JSON(w, http.StatusOK, list)
}

func parsePostID(s string) (int64, bool) {
	id, err := strconv.ParseInt(s, 10, 64)
	return id, err == nil
}
