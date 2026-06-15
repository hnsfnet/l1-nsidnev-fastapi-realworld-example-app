-- name: get-all-tags
SELECT tag
FROM tags;


-- name: create-new-tags*!
INSERT INTO tags (tag)
VALUES (:tag)
ON CONFLICT DO NOTHING;


-- name: get-popular-tags
SELECT att.tag,
       COUNT(att.article_id) AS article_count
FROM articles_to_tags att
         INNER JOIN articles a ON a.id = att.article_id
GROUP BY att.tag
ORDER BY article_count DESC, att.tag ASC
LIMIT :limit;
