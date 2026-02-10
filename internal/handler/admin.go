package handler

import (
	"net/http"
	"strconv"

	"ppp/api/internal/mock"
	"ppp/api/internal/response"
)

// AdminAuthLogin handles POST /admin/auth/login.
func (h *Handler) AdminAuthLogin(w http.ResponseWriter, r *http.Request) {
	if !h.Config.UseMock {
		response.NotImplemented(w)
		return
	}
	var body mock.AuthLoginRequest
	if err := decodeJSON(r, &body); err != nil {
		response.BadRequest(w, "invalid body")
		return
	}
	// Mock: accept any login/password
	resp := mock.AuthLogin(body.Login, body.Password)
	response.JSON(w, http.StatusOK, resp)
}

// AdminAuthRefresh handles POST /admin/auth/refresh.
func (h *Handler) AdminAuthRefresh(w http.ResponseWriter, r *http.Request) {
	if !h.Config.UseMock {
		response.NotImplemented(w)
		return
	}
	var body mock.AuthRefreshRequest
	_ = decodeJSON(r, &body)
	resp := mock.AuthRefresh(body.RefreshToken)
	response.JSON(w, http.StatusOK, resp)
}

// AdminDashboard handles GET /admin/dashboard.
func (h *Handler) AdminDashboard(w http.ResponseWriter, r *http.Request) {
	if !h.Config.UseMock {
		response.NotImplemented(w)
		return
	}
	response.JSON(w, http.StatusOK, mock.Dashboard())
}

// AdminUsersList handles GET /admin/users.
func (h *Handler) AdminUsersList(w http.ResponseWriter, r *http.Request) {
	if !h.Config.UseMock {
		response.NotImplemented(w)
		return
	}
	skip, _ := strconv.Atoi(r.URL.Query().Get("skip"))
	limit, _ := strconv.Atoi(r.URL.Query().Get("limit"))
	if limit <= 0 {
		limit = 20
	}
	response.JSON(w, http.StatusOK, mock.AdminUsersList(skip, limit))
}

// AdminUsersPatch handles PATCH /admin/users/{user_id}.
func (h *Handler) AdminUsersPatch(w http.ResponseWriter, r *http.Request, userID int64) {
	if !h.Config.UseMock {
		response.NotImplemented(w)
		return
	}
	if hasField(r) {
		response.JSON(w, http.StatusOK, mock.UserByID(userID))
		return
	}
	response.NoContent(w)
}

// AdminChannelsList handles GET /admin/channels.
func (h *Handler) AdminChannelsList(w http.ResponseWriter, r *http.Request) {
	if !h.Config.UseMock {
		response.NotImplemented(w)
		return
	}
	skip, _ := strconv.Atoi(r.URL.Query().Get("skip"))
	limit, _ := strconv.Atoi(r.URL.Query().Get("limit"))
	if limit <= 0 {
		limit = 20
	}
	response.JSON(w, http.StatusOK, mock.AdminChannelsList(skip, limit))
}

// AdminMLClustersRecalculate handles POST /admin/ml/clusters/recalculate.
func (h *Handler) AdminMLClustersRecalculate(w http.ResponseWriter, r *http.Request) {
	if !h.Config.UseMock {
		response.NotImplemented(w)
		return
	}
	response.JSON(w, http.StatusOK, map[string]any{"ok": true, "message": "clusters recalculated"})
}

// AdminMLClustersStats handles GET /admin/ml/clusters/stats.
func (h *Handler) AdminMLClustersStats(w http.ResponseWriter, r *http.Request) {
	if !h.Config.UseMock {
		response.NotImplemented(w)
		return
	}
	response.JSON(w, http.StatusOK, mock.ClustersStats())
}
