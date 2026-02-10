package handler

import "net/http"

// hasField returns true if request has non-empty "field" query parameter.
func hasField(r *http.Request) bool {
	return r.URL.Query().Get("field") != ""
}
