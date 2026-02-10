package mock

import (
	"strconv"
	"time"
)

const isoLayout = "2006-01-02T15:04:05Z07:00"

func nowISO() string { return time.Now().UTC().Format(isoLayout) }

// Root returns GET / response.
func Root() RootResponse {
	return RootResponse{
		Service: "Core API (personalized-post-platform)",
		Docs:    "/docs",
		Health:  "/health",
		Links:   []string{"/api/v1", "/docs", "/health"},
	}
}

// UserByTelegramID returns a mock user (GET /users/{telegram_id}).
func UserByTelegramID(telegramID int64) User {
	u := "johndoe"
	fn, ln := "John", "Doe"
	return User{
		ID:         1,
		TelegramID: telegramID,
		Username:   &u,
		FirstName:  &fn,
		LastName:   &ln,
		Status:     "active",
		Role:       "member",
		Language:   "en_US",
		CreatedAt:  "2024-01-15T10:00:00Z",
		UpdatedAt:  nowISO(),
	}
}

// UserCreate returns mock user for POST /users (same shape as get).
func UserCreate(telegramID int64) User {
	return UserByTelegramID(telegramID)
}

// UserByID returns a mock user by internal ID (for admin PATCH response).
func UserByID(id int64) User {
	u := UserByTelegramID(id)
	u.ID = id
	return u
}

// ChannelsList returns mock channels (GET /channels).
func ChannelsList(defaultsOnly bool) []Channel {
	u1, u2 := "durov", "telegram"
	list := []Channel{
		{
			ID:         1,
			TelegramID: 123456789,
			Username:   &u1,
			Title:      "Durov",
			IsDefault:  true,
			CreatedAt:  "2024-01-01T00:00:00Z",
			UpdatedAt:  nowISO(),
		},
		{
			ID:         2,
			TelegramID: 987654321,
			Username:   &u2,
			Title:      "Telegram",
			IsDefault:  true,
			CreatedAt:  "2024-01-01T00:00:00Z",
			UpdatedAt:  nowISO(),
		},
	}
	if defaultsOnly {
		return list
	}
	u3 := "sample"
	list = append(list, Channel{
		ID:         3,
		TelegramID: 111222333,
		Username:   &u3,
		Title:      "Sample Channel",
		IsDefault:  false,
		CreatedAt:  "2024-02-01T00:00:00Z",
		UpdatedAt:  nowISO(),
	})
	return list
}

// ChannelsUser returns GET /channels/user/{telegram_id} (channels for user).
func ChannelsUser(telegramID int64) []Channel {
	return ChannelsList(true)
}

// ChannelByID returns one channel (GET /channels/{id}).
func ChannelByID(channelID int64) Channel {
	u := "durov"
	return Channel{
		ID:         channelID,
		TelegramID: 123456789,
		Username:   &u,
		Title:      "Durov",
		IsDefault:  true,
		CreatedAt:  "2024-01-01T00:00:00Z",
		UpdatedAt:  nowISO(),
	}
}

// PostsCreate returns POST /posts response.
func PostsCreate(count int) PostsCreateResponse {
	ids := make([]int64, count)
	for i := 0; i < count; i++ {
		ids[i] = int64(100 + i)
	}
	return PostsCreateResponse{CreatedCount: count, PostIDs: ids}
}

// PostByID returns GET /posts/{id} metadata.
func PostByID(postID int64) Post {
	pt := "photo"
	return Post{
		ID:                postID,
		ChannelID:         1,
		TelegramMessageID:  42,
		MediaType:         &pt,
		PostedAt:          "2024-02-01T12:00:00Z",
		CreatedAt:         "2024-02-01T12:00:01Z",
		UpdatedAt:         nowISO(),
	}
}

// PostContentByID returns GET /posts/{id}/content.
func PostContentByID(postID int64) PostContent {
	mt := "photo"
	fid := "AgACAgIAAxkB"
	return PostContent{
		Text:        "Mock post text for post " + strconv.FormatInt(postID, 10),
		MediaType:   &mt,
		MediaFileID: &fid,
		CachedAt:    strPtr(nowISO()),
	}
}

func strPtr(s string) *string { return &s }

// PostsTraining returns POST /posts/training response.
func PostsTraining(telegramID int64, channelIDs []int64, postsPerChannel int) []PostWithChannel {
	var out []PostWithChannel
	pid := int64(1)
	for _, cid := range channelIDs {
		ch := ChannelByID(cid)
		for i := 0; i < postsPerChannel && i < 3; i++ {
			pt := "photo"
			out = append(out, PostWithChannel{
				Post: Post{
					ID:                pid,
					ChannelID:         cid,
					TelegramMessageID: int64(100 + i),
					MediaType:         &pt,
					PostedAt:          nowISO(),
					CreatedAt:         nowISO(),
					UpdatedAt:         nowISO(),
				},
				Channel: ch,
			})
			pid++
		}
	}
	if len(out) == 0 {
		out = append(out, PostWithChannel{Post: PostByID(1), Channel: ChannelByID(1)})
	}
	return out
}

// InteractionsList returns GET /interactions/{telegram_id}.
func InteractionsList(telegramID int64) []Interaction {
	return []Interaction{
		{ID: 1, UserID: 1, PostID: 10, InteractionType: "like", CreatedAt: "2024-02-01T10:00:00Z"},
		{ID: 2, UserID: 1, PostID: 11, InteractionType: "dislike", CreatedAt: "2024-02-01T10:01:00Z"},
	}
}

// MLTrain returns POST /ml/train response.
func MLTrain() MLTrainResponse {
	return MLTrainResponse{OK: true, Message: "Model trained successfully"}
}

// AuthLogin returns POST /admin/auth/login response.
func AuthLogin(login, password string) AuthLoginResponse {
	return AuthLoginResponse{
		AccessToken:  "mock_jwt_access_token_" + login,
		RefreshToken: "mock_refresh_token_" + login,
		ExpiresIn:    86400,
	}
}

// AuthRefresh returns POST /admin/auth/refresh response.
func AuthRefresh(refreshToken string) AuthLoginResponse {
	return AuthLoginResponse{
		AccessToken: "mock_jwt_refreshed",
		ExpiresIn:   86400,
	}
}

// Dashboard returns GET /admin/dashboard.
func Dashboard() DashboardResponse {
	return DashboardResponse{
		Overview: map[string]any{
			"users_total":   150,
			"channels_total": 10,
			"posts_total":   500,
		},
		Daily: map[string]any{
			"new_users":  5,
			"new_posts":  20,
		},
		Channels: ChannelsList(false),
		Retention: map[string]any{
			"day1": 0.8,
			"day7": 0.5,
		},
		Recommendations: map[string]any{
			"delivered_today": 100,
		},
	}
}

// AdminUsersList returns GET /admin/users (paginated).
func AdminUsersList(skip, limit int) []User {
	var list []User
	for i := 0; i < limit && i < 5; i++ {
		tid := int64(skip + i + 1)
		list = append(list, UserByTelegramID(tid))
	}
	return list
}

// AdminChannelsList returns GET /admin/channels.
func AdminChannelsList(skip, limit int) []Channel {
	all := ChannelsList(false)
	if skip >= len(all) {
		return nil
	}
	end := skip + limit
	if end > len(all) {
		end = len(all)
	}
	return all[skip:end]
}

// ClustersStats returns GET /admin/ml/clusters/stats.
func ClustersStats() ClustersStatsResponse {
	return ClustersStatsResponse{
		ClustersCount: 3,
		Channels: []ClusterChannel{
			{ChannelID: 1, Clusters: 2},
			{ChannelID: 2, Clusters: 1},
		},
	}
}
