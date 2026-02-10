package mock

// RootResponse is returned by GET /.
type RootResponse struct {
	Service string   `json:"service"`
	Docs    string   `json:"docs"`
	Health  string   `json:"health"`
	Links   []string `json:"links,omitempty"`
}

// User is the user entity (API response shape).
type User struct {
	ID          int64   `json:"id"`
	TelegramID  int64   `json:"telegram_id"`
	Username    *string `json:"username,omitempty"`
	FirstName   *string `json:"first_name,omitempty"`
	LastName    *string `json:"last_name,omitempty"`
	Status      string  `json:"status"`
	Role        string  `json:"role"`
	Language    string  `json:"language"`
	CreatedAt   string  `json:"created_at"`
	UpdatedAt   string  `json:"updated_at"`
	IsDeleted   bool    `json:"is_deleted,omitempty"`
	DeletedAt   *string `json:"deleted_at,omitempty"`
}

// Channel is the channel entity.
type Channel struct {
	ID         int64   `json:"id"`
	TelegramID int64   `json:"telegram_id"`
	Username   *string `json:"username,omitempty"`
	Title      string  `json:"title"`
	IsDefault  bool    `json:"is_default"`
	CreatedAt  string  `json:"created_at"`
	UpdatedAt  string  `json:"updated_at"`
	IsDeleted  bool    `json:"is_deleted,omitempty"`
	DeletedAt  *string `json:"deleted_at,omitempty"`
}

// Post is the post metadata entity.
type Post struct {
	ID                 int64   `json:"id"`
	ChannelID          int64   `json:"channel_id"`
	TelegramMessageID  int64   `json:"telegram_message_id"`
	MediaType          *string `json:"media_type,omitempty"`
	PostedAt           string  `json:"posted_at"`
	CreatedAt          string  `json:"created_at"`
	UpdatedAt          string  `json:"updated_at"`
	IsDeleted          bool    `json:"is_deleted,omitempty"`
	DeletedAt          *string `json:"deleted_at,omitempty"`
}

// PostContent is returned by GET /posts/{id}/content.
type PostContent struct {
	Text           string  `json:"text"`
	MediaType      *string `json:"media_type,omitempty"`
	MediaFileID    *string `json:"media_file_id,omitempty"`
	MediaDataBase64 *string `json:"media_data_base64,omitempty"`
	CachedAt       *string `json:"cached_at,omitempty"`
}

// PostsCreateRequest body for POST /posts.
type PostsCreateRequest struct {
	ChannelID int64   `json:"channel_id"`
	Posts     []PostItem `json:"posts"`
}

// PostItem is one item in bulk post create.
type PostItem struct {
	TelegramMessageID int64   `json:"telegram_message_id"`
	Text              *string `json:"text,omitempty"`
	MediaType         *string `json:"media_type,omitempty"`
	MediaFileID       *string `json:"media_file_id,omitempty"`
	PostedAt          string  `json:"posted_at"`
}

// PostsCreateResponse is returned by POST /posts.
type PostsCreateResponse struct {
	CreatedCount int     `json:"created_count"`
	PostIDs      []int64 `json:"post_ids"`
}

// Interaction is one user-post interaction.
type Interaction struct {
	ID             int64  `json:"id"`
	UserID         int64  `json:"user_id"`
	PostID         int64  `json:"post_id"`
	InteractionType string `json:"interaction_type"` // like, dislike, skip
	CreatedAt      string `json:"created_at"`
}

// UserChannel is user-channel subscription.
type UserChannel struct {
	ID          int64  `json:"id"`
	UserID      int64  `json:"user_id"`
	ChannelID   int64  `json:"channel_id"`
	IsBonus     bool   `json:"is_bonus"`
	MailingEnabled bool `json:"mailing_enabled"`
	CreatedAt   string `json:"created_at"`
}

// PostsTrainingRequest body for POST /posts/training.
type PostsTrainingRequest struct {
	TelegramID       int64   `json:"telegram_id"`
	ChannelIDs       []int64 `json:"channel_ids"`
	PostsPerChannel  int     `json:"posts_per_channel"`
}

// PostWithChannel for training response.
type PostWithChannel struct {
	Post    Post    `json:"post"`
	Channel Channel `json:"channel"`
}

// MLTrainResponse for POST /ml/train.
type MLTrainResponse struct {
	OK      bool   `json:"ok"`
	Message string `json:"message"`
}

// AuthLoginRequest for POST /admin/auth/login.
type AuthLoginRequest struct {
	Login    string `json:"login"`
	Password string `json:"password"`
}

// AuthLoginResponse for POST /admin/auth/login.
type AuthLoginResponse struct {
	AccessToken  string `json:"access_token"`
	RefreshToken string `json:"refresh_token,omitempty"`
	ExpiresIn    int    `json:"expires_in"` // seconds
}

// AuthRefreshRequest for POST /admin/auth/refresh.
type AuthRefreshRequest struct {
	RefreshToken string `json:"refresh_token"`
}

// DashboardResponse for GET /admin/dashboard.
type DashboardResponse struct {
	Overview       map[string]any `json:"overview"`
	Daily          map[string]any `json:"daily"`
	Channels       []Channel      `json:"channels"`
	Retention      map[string]any `json:"retention"`
	Recommendations map[string]any `json:"recommendations"`
}

// ClustersStatsResponse for GET /admin/ml/clusters/stats.
type ClustersStatsResponse struct {
	ClustersCount int            `json:"clusters_count"`
	Channels      []ClusterChannel `json:"channels,omitempty"`
}

// ClusterChannel for cluster stats.
type ClusterChannel struct {
	ChannelID int64 `json:"channel_id"`
	Clusters  int   `json:"clusters"`
}
