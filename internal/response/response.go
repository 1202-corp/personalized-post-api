package response

import (
	"encoding/json"
	"net/http"
)

// JSON writes v as JSON with status code.
func JSON(w http.ResponseWriter, status int, v any) {
	w.Header().Set("Content-Type", "application/json; charset=utf-8")
	w.WriteHeader(status)
	if v != nil {
		_ = json.NewEncoder(w).Encode(v)
	}
}

// NoContent sends 204 No Content.
func NoContent(w http.ResponseWriter) {
	w.WriteHeader(http.StatusNoContent)
}

// ErrorDetail is the standard error body.
type ErrorDetail struct {
	Detail string `json:"detail"`
}

// Error writes a JSON error response.
func Error(w http.ResponseWriter, status int, detail string) {
	JSON(w, status, ErrorDetail{Detail: detail})
}

// BadRequest writes 400.
func BadRequest(w http.ResponseWriter, detail string) {
	Error(w, http.StatusBadRequest, detail)
}

// NotFound writes 404.
func NotFound(w http.ResponseWriter, detail string) {
	Error(w, http.StatusNotFound, detail)
}

// Conflict writes 409.
func Conflict(w http.ResponseWriter, detail string) {
	Error(w, http.StatusConflict, detail)
}

// InternalServerError writes 500.
func InternalServerError(w http.ResponseWriter, detail string) {
	Error(w, http.StatusInternalServerError, detail)
}

// NotImplemented writes 501.
func NotImplemented(w http.ResponseWriter) {
	Error(w, http.StatusNotImplemented, "not implemented")
}
