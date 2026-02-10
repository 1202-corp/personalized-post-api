package handler

import (
	"net/http"

	"github.com/go-chi/chi/v5"
)

// Routes returns the chi router with all routes mounted.
func (h *Handler) Routes() http.Handler {
	r := chi.NewRouter()

	r.Get("/", h.Root)
	r.Get("/health", h.Health)
	r.Get("/docs", h.Docs)
	r.Get("/docs/openapi.yaml", h.DocsOpenAPI)

	r.Route("/api/v1", func(r chi.Router) {
		// Users
		r.Post("/users", h.UsersCreate)
		r.Get("/users/{telegram_id}", h.usersGetByID)
		r.Patch("/users/{telegram_id}", h.usersPatchByID)
		r.Delete("/users/{telegram_id}", h.usersDeleteByID)

		// Channels
		r.Post("/channels", h.ChannelsCreate)
		r.Get("/channels", h.ChannelsList)
		r.Get("/channels/{channel_id}", h.channelsGetByID)
		r.Post("/channels/user", h.ChannelsUserAdd)
		r.Get("/channels/user/{telegram_id}", h.channelsUserListByID)

		// Posts
		r.Post("/posts", h.PostsCreate)
		r.Get("/posts/{post_id}", h.postsGetByID)
		r.Get("/posts/{post_id}/content", h.postsContentByID)
		r.Post("/posts/training", h.PostsTraining)

		// Interactions
		r.Post("/interactions", h.InteractionsCreate)
		r.Get("/interactions/{telegram_id}", h.interactionsListByID)
		r.Delete("/interactions/{telegram_id}", h.interactionsDeleteByID)

		// ML
		r.Post("/ml/train", h.MLTrain)
	})

	r.Route("/admin", func(r chi.Router) {
		r.Post("/auth/login", h.AdminAuthLogin)
		r.Post("/auth/refresh", h.AdminAuthRefresh)
		r.Get("/dashboard", h.AdminDashboard)
		r.Get("/users", h.AdminUsersList)
		r.Patch("/users/{user_id}", h.adminUsersPatchByID)
		r.Get("/channels", h.AdminChannelsList)
		r.Post("/ml/clusters/recalculate", h.AdminMLClustersRecalculate)
		r.Get("/ml/clusters/stats", h.AdminMLClustersStats)
	})

	return r
}

func (h *Handler) usersGetByID(w http.ResponseWriter, r *http.Request) {
	id, ok := parseTelegramID(chi.URLParam(r, "telegram_id"))
	if !ok {
		h.UsersGet(w, r, 123456789)
		return
	}
	h.UsersGet(w, r, id)
}

func (h *Handler) usersPatchByID(w http.ResponseWriter, r *http.Request) {
	id, ok := parseTelegramID(chi.URLParam(r, "telegram_id"))
	if !ok {
		h.UsersPatch(w, r, 123456789)
		return
	}
	h.UsersPatch(w, r, id)
}

func (h *Handler) usersDeleteByID(w http.ResponseWriter, r *http.Request) {
	id, ok := parseTelegramID(chi.URLParam(r, "telegram_id"))
	if !ok {
		h.UsersDelete(w, r, 123456789)
		return
	}
	h.UsersDelete(w, r, id)
}

func (h *Handler) channelsGetByID(w http.ResponseWriter, r *http.Request) {
	id, ok := parseChannelID(chi.URLParam(r, "channel_id"))
	if !ok {
		id = 1
	}
	h.ChannelsGet(w, r, id)
}

func (h *Handler) channelsUserListByID(w http.ResponseWriter, r *http.Request) {
	id, ok := parseTelegramID(chi.URLParam(r, "telegram_id"))
	if !ok {
		id = 123456789
	}
	h.ChannelsUserList(w, r, id)
}

func (h *Handler) postsGetByID(w http.ResponseWriter, r *http.Request) {
	id, ok := parsePostID(chi.URLParam(r, "post_id"))
	if !ok {
		id = 1
	}
	h.PostsGet(w, r, id)
}

func (h *Handler) postsContentByID(w http.ResponseWriter, r *http.Request) {
	id, ok := parsePostID(chi.URLParam(r, "post_id"))
	if !ok {
		id = 1
	}
	h.PostsContent(w, r, id)
}

func (h *Handler) interactionsListByID(w http.ResponseWriter, r *http.Request) {
	id, ok := parseTelegramID(chi.URLParam(r, "telegram_id"))
	if !ok {
		id = 123456789
	}
	h.InteractionsList(w, r, id)
}

func (h *Handler) interactionsDeleteByID(w http.ResponseWriter, r *http.Request) {
	id, ok := parseTelegramID(chi.URLParam(r, "telegram_id"))
	if !ok {
		id = 123456789
	}
	h.InteractionsDelete(w, r, id)
}

func (h *Handler) adminUsersPatchByID(w http.ResponseWriter, r *http.Request) {
	id, ok := parseUserID(chi.URLParam(r, "user_id"))
	if !ok {
		id = 1
	}
	h.AdminUsersPatch(w, r, id)
}
